import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm
import yfinance as yf
import os
import io
import time

# --- 1. CONFIGURACIÓN DE ENTORNO ---
st.set_page_config(
    page_title="COST Institutional Terminal | v2.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Profesional: Estilo Terminal Bloomberg / Refinitiv
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stMetric { 
        background-color: rgba(255, 255, 255, 0.05); 
        padding: 20px; 
        border-radius: 12px; 
        border: 1px solid #30363d; 
    }
    .scenario-card { 
        background-color: #1c2128; 
        border-radius: 15px; 
        padding: 25px; 
        border: 1px solid #444c56; 
        text-align: center; 
    }
    .metric-costco { color: #ffffff; font-size: 36px; font-weight: bold; margin: 10px 0; }
    .label-bajista { color: #f85149; background-color: rgba(248, 81, 73, 0.15); padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: bold; }
    .label-base { color: #dbab09; background-color: rgba(219, 171, 9, 0.15); padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: bold; }
    .label-alcista { color: #3fb950; background-color: rgba(63, 185, 80, 0.15); padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: bold; }
    /* Estilo de pestañas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
        color: #8b949e;
    }
    .stTabs [aria-selected="true"] { background-color: #005BAA !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE SEGURIDAD Y CÁLCULO ---

def clamp(value, min_val, max_val):
    """Garantiza que los datos dinámicos no rompan los sliders de Streamlit."""
    try:
        return float(max(min(value, max_val), min_val))
    except:
        return min_val

@st.cache_data(ttl=3600)
def fetch_institutional_data(ticker):
    """Descarga y procesa datos crudos de la SEC vía Yahoo Finance."""
    try:
        asset = yf.Ticker(ticker)
        info = asset.info
        cf = asset.cashflow
        
        # Extracción de Precio y Riesgo (Beta)
        current_price = info.get('currentPrice', 950.0)
        market_beta = info.get('beta', 0.79)
        
        # Cálculo de FCF Real: Operating Cash Flow + Capital Expenditure
        # (Nota: CapEx suele venir como negativo en la API)
        fcf_series = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']) / 1e9
        
        # Cálculo de Crecimiento Compuesto (CAGR) de los últimos 4 años
        f_vals = fcf_series.values[::-1]
        if len(f_vals) > 1:
            growth_rate = (f_vals[-1] / f_vals[0])**(1/(len(f_vals)-1)) - 1
        else:
            growth_rate = 0.12 # Valor por defecto defensivo para COST
            
        return {
            "name": info.get('longName', 'Costco Wholesale Corp'),
            "price": current_price,
            "beta": market_beta,
            "fcf_last": fcf_series.iloc[0],
            "fcf_history": fcf_series,
            "avg_growth": growth_rate,
            "is": asset.financials,
            "bs": asset.balance_sheet,
            "cf": cf,
            "mkt_cap": info.get('marketCap', 450e9) / 1e9
        }
    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        return None

def dcf_valuation_engine(fcf, g1, g2, wacc, gt, shares=0.4436, cash=22.0):
    """Modelo de Descuento de Flujos de Caja en 2 Etapas."""
    future_flows = []
    current_fcf = fcf
    for year in range(1, 11):
        # Etapa 1: Crecimiento Alto | Etapa 2: Transición
        current_fcf *= (1 + g1) if year <= 5 else (1 + g2)
        future_flows.append(current_fcf)
        
    # Descuento de flujos proyectados
    pv_flows = sum([f / (1 + wacc)**i for i, f in enumerate(future_flows, 1)])
    
    # Cálculo de Valor Terminal (Modelo Gordon Growth)
    terminal_value = (future_flows[-1] * (1 + gt)) / (wacc - gt)
    pv_terminal = terminal_value / (1 + wacc)**10
    
    intrinsic_value = ((pv_flows + pv_terminal) / shares) + cash
    return intrinsic_value, future_flows, pv_flows, pv_terminal

def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    """Calculador de Griegas para gestión de riesgo con opciones."""
    T = max(T, 0.0001)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    theta = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d2 if option_type=='call' else -d2)) / 365
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# --- 3. INTERFAZ Y CONTROL ---

def main():
    # Carga de Datos con Spinner Institucional
    with st.spinner("Estableciendo conexión con servidores de datos financieros..."):
        data = fetch_institutional_data("COST")
        if not data: return

    # --- SIDEBAR: PANEL DE CONTROL ---
    st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Costco_Wholesale_logo_2010-2014.svg/2560px-Costco_Wholesale_logo_2010-2014.svg.png", width=200)
    st.sidebar.markdown("### ⚙️ Parámetros del Modelo")
    
    # PROTECCIÓN ANTI-VALUEERROR (Clamping de seguridad)
    fcf_init = clamp(data['fcf_last'], 0.0, 50.0)
    g1_init = clamp(data['avg_growth'] * 100, 0.0, 45.0)
    
    fcf_base = st.sidebar.slider("FCF Base ($B)", 0.0, 50.0, fcf_init)
    g1_growth = st.sidebar.slider("Crecimiento 1-5Y (%)", 0.0, 45.0, g1_init) / 100
    g2_growth = st.sidebar.slider("Crecimiento 6-10Y (%)", 0.0, 20.0, 8.0) / 100
    wacc = st.sidebar.slider("WACC / Descuento (%)", 4.0, 15.0, 8.5) / 100
    
    # Datos Adicionales en Sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Supuestos Macro")
    risk_free = st.sidebar.number_input("Tasa Libre de Riesgo (%)", value=4.25) / 100
    market_premium = st.sidebar.number_input("Prima Riesgo Mercado (%)", value=5.5) / 100

    # CÁLCULOS CENTRALES
    v_fair, flows, pv_f, pv_t = dcf_valuation_engine(fcf_base, g1_growth, g2_growth, wacc, 0.025)
    upside = (v_fair / data['price'] - 1) * 100

    # --- UI: HEADER DE MERCADO ---
    st.title(f"🏛️ {data['name']} Intelligence Terminal")
    
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)
    with col_h1:
        st.metric("Precio Mercado", f"${data['price']:.2f}")
    with col_h2:
        color = "normal" if upside > 0 else "inverse"
        st.metric("Valor Intrínseco", f"${v_fair:.2f}", f"{upside:.1f}% Upside", delta_color=color)
    with col_h3:
        st.metric("Beta (Riesgo)", f"{data['beta']}", "Defensivo")
    with col_h4:
        st.metric("Market Cap", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- SISTEMA DE PESTAÑAS (7 TABS) ---
    tabs = st.tabs([
        "📋 Resumen Ejecutivo", "💎 Valoración DCF", "📊 Benchmarking", 
        "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Opciones Lab", "📥 Data Export"
    ])

    # TAB 1: RESUMEN DE ESCENARIOS
    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        # Lógica de Escenarios Dinámicos
        v_baj, _, _, _ = dcf_valuation_engine(fcf_base, g1_growth*0.6, g2_growth*0.5, wacc+0.015, 0.02)
        v_alc, _, _, _ = dcf_valuation_engine(fcf_base, g1_growth+0.04, g2_growth+0.02, wacc-0.01, 0.03)

        with c1:
            st.markdown(f'<div class="scenario-card"><span class="label-bajista">Bajista</span><div class="metric-costco">${v_baj:.0f}</div><small>WACC +150bps | G -50%</small></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="scenario-card"><span class="label-base">Caso Base</span><div class="metric-costco">${v_fair:.0f}</div><small>Supuestos del Analista</small></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="scenario-card"><span class="label-alcista">Alcista</span><div class="metric-costco">${v_alc:.0f}</div><small>WACC -100bps | G +400bps</small></div>', unsafe_allow_html=True)
        
        st.markdown("### Composición del Valor Presente")
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 1-10Y', 'PV Valor Terminal'], values=[pv_f, pv_t], hole=.5, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig_donut, use_container_width=True)

    # TAB 2: VALORACIÓN (BRIDGE HISTÓRICO)
    with tabs[1]:
        st.subheader("Puente de Datos: Histórico SEC vs Proyección del Analista")
        hist_years = [c.strftime('%Y') for c in data['fcf_history'].index[::-1]]
        hist_values = data['fcf_history'].values[::-1]
        proj_years = [str(int(hist_years[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        # Línea Histórica Real
        fig_bridge.add_trace(go.Scatter(x=hist_years, y=hist_values, name="Real (10-K)", line=dict(color='#005BAA', width=4), mode='lines+markers'))
        # Línea de Proyección
        fig_bridge.add_trace(go.Scatter(x=[hist_years[-1]] + proj_years, y=[hist_values[-1]] + flows, name="Proyección", line=dict(color='#E31837', dash='dash', width=4), mode='lines+markers'))
        
        fig_bridge.update_layout(template="plotly_dark", title="Trayectoria del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        [attachment_0](attachment)
        
        # Matriz de Sensibilidad
        st.markdown("### Matriz de Sensibilidad: WACC vs Crecimiento Perpetuo")
        w_range = np.linspace(wacc-0.015, wacc+0.015, 5)
        g_range = np.linspace(0.015, 0.035, 5)
        matrix = [[dcf_valuation_engine(fcf_base, g1_growth, g2_growth, w, g)[0] for g in g_range] for w in w_range]
        df_sens = pd.DataFrame(matrix, index=[f"W:{x*100:.1f}%" for x in w_range], columns=[f"g:{x*100:.1f}%" for x in g_range])
        st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    # TAB 3: BENCHMARKING
    with tabs[2]:
        peers = pd.DataFrame({
            'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500'],
            'PE': [51.8, 31.2, 17.5, 21.1, 45.0, 22.5],
            'ROE': [28.5, 14.2, 22.1, 45.3, 15.1, 18.0]
        })
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.plotly_chart(px.bar(peers, x='Ticker', y='PE', color='Ticker', title="Multiplo P/E Relativo", template="plotly_dark"), use_container_width=True)
        with col_b2:
            st.plotly_chart(px.scatter(peers, x='ROE', y='PE', text='Ticker', size='PE', title="Retorno sobre Capital vs Valuación", template="plotly_dark"), use_container_width=True)

    # TAB 4: MONTE CARLO
    with tabs[3]:
        st.subheader("Simulación Monte Carlo (1,000 Iteraciones)")
        vol_growth = st.slider("Volatilidad de Pronóstico (Desviación G1)", 0.01, 0.10, 0.03)
        
        # Simulación de vectores
        mc_results = []
        for _ in range(1000):
            sim_g = np.random.normal(g1_growth, vol_growth)
            sim_w = np.random.normal(wacc, 0.005)
            val, _, _, _ = dcf_valuation_engine(fcf_base, sim_g, g2_growth, sim_w, 0.025)
            mc_results.append(val)
        
        prob_success = (np.array(mc_results) > data['price']).mean() * 100
        fig_mc = px.histogram(mc_results, nbins=50, title=f"Probabilidad de Infravaloración: {prob_success:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=data['price'], line_color="#f85149", line_dash="dash", annotation_text="Precio Actual")
        st.plotly_chart(fig_mc, use_container_width=True)
        
        [attachment_1](attachment)

    # TAB 5: STRESS TEST LAB
    with tabs[4]:
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        cs1, cs2 = st.columns(2)
        with cs1:
            s_consumo = st.slider("Shock Consumo Discrecional (%)", -20, 10, 0)
            s_supply = st.slider("Disrupción Logística (Coste %)", 0, 15, 0)
        with cs2:
            s_rates = st.slider("Alza de Tasas FED (bps)", 0, 500, 0)
            s_labor = st.slider("Inflación Salarial (%)", 0, 10, 0)
            
        # Lógica de Estrés: El WACC sube con las tasas y el crecimiento cae con el consumo
        adj_g = g1_growth + (s_consumo/200) - (s_supply/1000)
        adj_w = wacc + (s_rates/20000) + (s_labor/2000)
        v_stress, _, _, _ = dcf_valuation_engine(fcf_base, adj_g, g2_growth, adj_w, 0.02)
        
        delta_stress = (v_stress / v_fair - 1) * 100
        st.metric("Valor Post-Stress Test", f"${v_stress:.2f}", f"{delta_stress:.1f}% vs Base")

    # TAB 6: OPCIONES LAB
    with tabs[5]:
        st.subheader("Estrategias de Cobertura y Generación de Yield")
        strike = st.number_input("Precio de Ejercicio (Strike)", value=float(round(data['price']*1.05, 0)))
        iv = st.slider("Volatilidad Implícita (%)", 10, 100, 25) / 100
        
        greeks = black_scholes_greeks(data['price'], strike, 45/365, risk_free, iv)
        
        go1, go2, go3, go4 = st.columns(4)
        go1.metric("Prima Estimada", f"${greeks['price']:.2f}")
        go2.metric("Delta (Δ)", f"{greeks['delta']:.3f}")
        go3.metric("Vega (ν)", f"{greeks['vega']:.3f}")
        go4.metric("Theta (θ/día)", f"${greeks['theta']:.2f}")

    # TAB 7: EXCEL EXPORT
    with tabs[6]:
        st.subheader("Descarga de Reporte Institucional")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Consolidar Estados Financieros
            data['is'].to_excel(writer, sheet_name='Income_Statement')
            data['bs'].to_excel(writer, sheet_name='Balance_Sheet')
            data['cf'].to_excel(writer, sheet_name='Cash_Flow')
            # Ratios y Proyecciones
            pd.DataFrame({"Año": proj_years, "FCF_Proj": flows}).to_excel(writer, sheet_name='Projections')
            
        st.download_button(
            label="💾 Generar y Descargar Master Excel (3-Statement Model)",
            data=buffer.getvalue(),
            file_name=f"COST_Analysis_{time.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
