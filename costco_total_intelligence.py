import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm
import yfinance as yf
import os
import io
import datetime

# --- 1. CONFIGURACIÓN DE ENTORNO Y ESTILO ---
# Establecemos el layout ancho y el título de la pestaña del navegador
st.set_page_config(
    page_title="COST Institutional Terminal Pro",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de CSS para simular una Terminal Bloomberg / Reuters
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stMetric { 
        background-color: rgba(255, 255, 255, 0.05); 
        padding: 20px; border-radius: 12px; border: 1px solid #30363d; 
    }
    .scenario-card { 
        background-color: #1c2128; border-radius: 15px; padding: 25px; 
        border: 1px solid #444c56; text-align: center; 
    }
    .metric-costco { color: #ffffff; font-size: 38px; font-weight: bold; margin: 10px 0; }
    .label-bajista { color: #f85149; background-color: rgba(248, 81, 73, 0.15); padding: 5px 15px; border-radius: 20px; font-weight: bold; }
    .label-base { color: #dbab09; background-color: rgba(219, 171, 9, 0.15); padding: 5px 15px; border-radius: 20px; font-weight: bold; }
    .label-alcista { color: #3fb950; background-color: rgba(63, 185, 80, 0.15); padding: 5px 15px; border-radius: 20px; font-weight: bold; }
    /* Personalización de Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #161b22;
        border-radius: 8px 8px 0px 0px; color: #8b949e; border: 1px solid #30363d;
    }
    .stTabs [aria-selected="true"] { background-color: #005BAA !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES DE DATOS Y CÁLCULO ---

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    """Extrae datos financieros reales y calcula métricas de crecimiento."""
    try:
        asset = yf.Ticker(ticker_symbol)
        info = asset.info
        cf = asset.cashflow
        
        # Cálculo de Free Cash Flow (FCF): Flujo Operativo + Inversiones de Capital (CapEx)
        # CapEx suele ser negativo, por eso sumamos.
        fcf_series = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']) / 1e9
        
        # Cálculo de CAGR (Crecimiento Anual Compuesto) histórico
        vals = fcf_series.values[::-1]
        if len(vals) > 1 and vals[0] > 0:
            growth_calc = (vals[-1] / vals[0])**(1/(len(vals)-1)) - 1
        else:
            growth_calc = 0.12 # Valor estándar de seguridad para Costco
            
        return {
            "name": info.get('longName', 'Costco Wholesale Corp'),
            "price": info.get('currentPrice', 950.0),
            "beta": info.get('beta', 0.79),
            "fcf_last": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "growth_suggested": growth_calc,
            "pe_ratio": info.get('trailingPE', 51.8),
            "mkt_cap": info.get('marketCap', 450e9) / 1e9,
            "income_statement": asset.financials,
            "balance_sheet": asset.balance_sheet,
            "cash_flow": cf
        }
    except Exception as e:
        st.error(f"Error en la extracción de datos: {e}")
        return None

def run_dcf_model(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Ejecuta el modelo de descuento de flujos en dos etapas."""
    projections = []
    current_val = fcf
    for i in range(1, 11):
        # Años 1-5 crecimiento G1, años 6-10 crecimiento G2
        current_val *= (1 + g1) if i <= 5 else (1 + g2)
        projections.append(current_val)
    
    # Valor Presente de los flujos proyectados
    pv_flows = sum([f / (1 + wacc)**i for i, f in enumerate(projections, 1)])
    
    # Valor Terminal (Gordon Growth)
    terminal_val = (projections[-1] * (1 + gt)) / (wacc - gt)
    pv_terminal = terminal_val / (1 + wacc)**10
    
    fair_value = ((pv_flows + pv_terminal) / shares) + cash
    return fair_value, projections, pv_flows, pv_terminal

def calculate_greeks(S, K, T, r, sigma, option_type='call'):
    """Modelo Black-Scholes para análisis de opciones."""
    T = max(T, 0.0001)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        p = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        d = norm.cdf(d1)
    else:
        p = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        d = norm.cdf(d1) - 1
        
    g = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    v = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    th = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d1 if option_type=='call' else -d1)) / 365
    return {"price": p, "delta": d, "gamma": g, "vega": v, "theta": th}

# --- 3. LÓGICA DE INTERFAZ ---

def main():
    # Carga inicial de datos
    with st.spinner("Estableciendo conexión segura con Yahoo Finance y la SEC..."):
        data = load_institutional_data("COST")
        if not data: return

    # --- SIDEBAR: CONTROL DE VARIABLES (PROTEGIDO) ---
    st.sidebar.markdown("## ⚙️ Configuración del Modelo")
    
    # TRUCO ANTI-ERROR: Clipping de valores
    # Si el valor real se sale del rango, lo forzamos al límite para evitar el ValueError
    fcf_init = float(np.clip(data['fcf_last'], 0.0, 50.0))
    g1_init = float(np.clip(data['growth_suggested'] * 100, 0.0, 45.0))
    
    p_actual = st.sidebar.number_input("Precio de Mercado ($)", value=float(data['price']))
    fcf_base = st.sidebar.slider("FCF Base ($B)", 0.0, 50.0, fcf_init)
    g1_growth = st.sidebar.slider("Crecimiento Años 1-5 (%)", 0.0, 45.0, g1_init) / 100
    g2_growth = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0.0, 20.0, 8.0) / 100
    wacc_rate = st.sidebar.slider("Tasa de Descuento (WACC) %", 4.0, 15.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏛️ Datos de Calidad")
    st.sidebar.info(f"Beta: {data['beta']} | P/E: {data['pe_ratio']:.1f}x")
    
    # Botón de descarga de guía si existe
    if os.path.exists("Guia_Metodologica_COST.pdf"):
        with open("Guia_Metodologica_COST.pdf", "rb") as f:
            st.sidebar.download_button("📄 Guía Institucional", f, "Guia_Analisis.pdf")

    # CÁLCULOS CENTRALES
    v_intrinsic, projections, pv_f, pv_t = run_dcf_model(fcf_base, g1_growth, g2_growth, wacc_rate)
    margin_safety = (v_intrinsic / p_actual - 1) * 100

    # --- UI: DASHBOARD PRINCIPAL ---
    st.title(f"🏛️ {data['name']} Intelligence Terminal")
    st.caption(f"Datos en tiempo real via yFinance | Última actualización: {datetime.datetime.now().strftime('%H:%M:%S')}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precio Mercado", f"${p_actual:.2f}")
    c2.metric("Fair Value (DCF)", f"${v_intrinsic:.2f}", f"{margin_safety:.1f}% Upside")
    c3.metric("Beta (Riesgo)", f"{data['beta']}", "Defensivo")
    c4.metric("Market Cap", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- SISTEMA DE PESTAÑAS ---
    tabs = st.tabs(["📋 Resumen", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones Lab", "📥 Exportar"])

    with tabs[0]: # PESTAÑA RESUMEN
        col_res1, col_res2, col_res3 = st.columns(3)
        # Escenarios dinámicos
        v_baj, _, _, _ = run_dcf_model(fcf_base, g1_growth*0.6, g2_growth*0.5, wacc_rate+0.015)
        v_alc, _, _, _ = run_dcf_model(fcf_base, g1_growth+0.04, g2_growth+0.02, wacc_rate-0.01)

        col_res1.markdown(f'<div class="scenario-card"><span class="label-bajista">BAJISTA</span><div class="metric-costco">${v_baj:.0f}</div><small>Shock Consumo / Alza de Tasas</small></div>', unsafe_allow_html=True)
        col_res2.markdown(f'<div class="scenario-card"><span class="label-base">CASO BASE</span><div class="metric-costco">${v_intrinsic:.0f}</div><small>Supuestos del Analista</small></div>', unsafe_allow_html=True)
        col_res3.markdown(f'<div class="scenario-card"><span class="label-alcista">ALCISTA</span><div class="metric-costco">${v_alc:.0f}</div><small>Expansión Global / Membresía</small></div>', unsafe_allow_html=True)
        
        st.markdown("### Estructura de Valor Presente")
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'PV Valor Terminal'], values=[pv_f, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=400, showlegend=True)
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # PESTAÑA VALORACIÓN PRO
        st.subheader("Trayectoria de Generación de Caja: Histórico vs Proyectado")
        hist_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        hist_y = data['fcf_hist'].values[::-1]
        proj_x = [str(int(hist_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=hist_x, y=hist_y, name="Real (SEC)", line=dict(color='#005BAA', width=4), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[hist_x[-1]] + proj_x, y=[hist_y[-1]] + projections, name="Proyección", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", title="Evolución del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        

        st.markdown("### Sensibilidad: WACC vs Crecimiento Perpetuo (g)")
        w_range = np.linspace(wacc_rate-0.015, wacc_rate+0.015, 5)
        g_range = np.linspace(0.015, 0.035, 5)
        sens_matrix = [[run_dcf_model(fcf_base, g1_growth, g2_growth, w, g)[0] for g in g_range] for w in w_range]
        df_sens = pd.DataFrame(sens_matrix, index=[f"W:{x*100:.1f}%" for x in w_range], columns=[f"g:{x*100:.1f}%" for x in g_range])
        st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with tabs[2]: # PESTAÑA BENCHMARKING
        peers = pd.DataFrame({
            'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500'],
            'PE': [data['pe_ratio'], 31.2, 17.5, 21.1, 45.0, 22.5],
            'Growth': [data['growth_suggested']*100, 6.2, 4.5, 8.2, 12.5, 7.0]
        })
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.plotly_chart(px.bar(peers, x='Ticker', y='PE', color='Ticker', title="P/E Ratio Relativo", template="plotly_dark"), use_container_width=True)
        with col_b2:
            st.plotly_chart(px.scatter(peers, x='Growth', y='PE', text='Ticker', size='PE', title="Crecimiento vs Valuación", template="plotly_dark"), use_container_width=True)
        
        

    with tabs[3]: # PESTAÑA MONTE CARLO
        st.subheader("Simulación Estocástica de Valor Intrínseco")
        vol_inp = st.slider("Volatilidad de Supuestos (%)", 1, 10, 3) / 100
        sim_results = [run_dcf_model(fcf_base, np.random.normal(g1_growth, vol_inp), g2_growth, np.random.normal(wacc_rate, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sim_results) > p_actual).mean() * 100
        
        fig_mc = px.histogram(sim_results, nbins=50, title=f"Probabilidad de Upside: {prob_up:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_actual, line_color="#f85149", line_dash="dash", annotation_text="Precio Mercado")
        st.plotly_chart(fig_mc, use_container_width=True)
        
        

    with tabs[4]: # PESTAÑA STRESS TEST
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        cs1, cs2 = st.columns(2)
        with cs1:
            s_inc = st.slider("Shock Ingreso Disponible %", -15, 5, 0)
            s_u = st.slider("Alza Desempleo %", 3, 15, 4)
        with cs2:
            s_inf = st.slider("Inflación CPI %", 0, 12, 3)
            s_w = st.slider("Carga Salarial %", 0, 10, 4)
        
        # Ajuste dinámico de G y WACC basado en variables macro
        v_stress, _, _, _ = run_dcf_model(fcf_base, g1_growth+(s_inc/200)-(s_u/500), g2_growth, wacc_rate+(s_inf/500)+(s_w/1000))
        st.metric("Valor Post-Stress Test", f"${v_stress:.2f}", f"{(v_stress/v_intrinsic-1)*100:.1f}% vs Base")

    with tabs[5]: # PESTAÑA OPCIONES LAB
        st.subheader("Gestión de Riesgo y Griegas")
        k_strike = st.number_input("Precio Strike", value=float(round(p_actual*1.05, 0)))
        vol_impl = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        gr = calculate_greeks(p_actual, k_strike, 45/365, 0.045, vol_impl)
        
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Call (45D)", f"${gr['price']:.2f}")
        o2.metric("Delta (Δ)", f"{gr['delta']:.3f}")
        o3.metric("Vega (ν)", f"{gr['vega']:.4f}")
        o4.metric("Theta (θ/día)", f"${gr['theta']:.2f}")
        
        

    with tabs[6]: # PESTAÑA EXPORTAR
        st.subheader("Generación de Reporte de Datos Crudos")
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine='xlsxwriter') as writer:
            data['income_statement'].to_excel(writer, sheet_name='Income_Statement')
            data['balance_sheet'].to_excel(writer, sheet_name='Balance_Sheet')
            data['cash_flow'].to_excel(writer, sheet_name='Cash_Flow')
            pd.DataFrame({"Proyecciones": projections}).to_excel(writer, sheet_name='DCF_Model')
        st.download_button("💾 Descargar Master Excel (3-Statement Model)", xlsx_buf.getvalue(), f"COST_Model_{datetime.date.today()}.xlsx")

if __name__ == "__main__":
    main()
