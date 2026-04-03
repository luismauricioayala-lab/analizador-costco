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
st.set_page_config(
    page_title="COST Master Institutional",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo Bloomberg Terminal (Dark Mode Premium)
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
    .metric-costco { color: #ffffff; font-size: 36px; font-weight: bold; margin: 10px 0; }
    .label-bajista { color: #f85149; background-color: rgba(248, 81, 73, 0.15); padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    .label-base { color: #dbab09; background-color: rgba(219, 171, 9, 0.15); padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    .label-alcista { color: #3fb950; background-color: rgba(63, 185, 80, 0.15); padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AYUDANTES TÉCNICOS ---

def clamp(val, min_v, max_v):
    """Evita que la App explote si la data real supera los límites del slider."""
    return float(max(min(val, max_v), min_v))

@st.cache_data(ttl=3600)
def fetch_data(ticker_symbol):
    """Extrae y procesa estados financieros reales de la SEC."""
    try:
        asset = yf.Ticker(ticker_symbol)
        info = asset.info
        cf = asset.cashflow
        
        # Cálculo de FCF Real (Operating Cash Flow + Capital Expenditure)
        fcf_series = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']) / 1e9
        
        # Calcular Crecimiento Histórico (CAGR 3Y)
        vals = fcf_series.values[::-1]
        cagr = (vals[-1]/vals[0])**(1/(len(vals)-1)) - 1 if len(vals) > 1 else 0.12
        
        return {
            "name": info.get('longName', 'Costco Wholesale'),
            "price": info.get('currentPrice', 950.0),
            "beta": info.get('beta', 0.79),
            "fcf_last": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr": cagr,
            "pe": info.get('trailingPE', 51.8),
            "mkt_cap": info.get('marketCap', 450e9) / 1e9,
            "is": asset.financials,
            "bs": asset.balance_sheet,
            "cf": cf
        }
    except Exception as e:
        st.error(f"Error crítico de conexión: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt, shares=0.443, cash=22.0):
    """Motor de Valoración por Descuento de Flujos en 2 Etapas."""
    projections = []
    curr = fcf
    for i in range(1, 11):
        curr *= (1 + g1) if i <= 5 else (1 + g2)
        projections.append(curr)
    
    pv_flows = sum([f / (1 + wacc)**i for i, f in enumerate(projections, 1)])
    tv = (projections[-1] * (1 + gt)) / (wacc - gt)
    pv_tv = tv / (1 + wacc)**10
    
    fair_v = ((pv_flows + pv_tv) / shares) + cash
    return fair_v, projections, pv_flows, pv_tv

def get_greeks(S, K, T, r, sigma, o_type='call'):
    """Cálculo de Griegas Black-Scholes para gestión de riesgo."""
    T = max(T, 0.0001)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if o_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    theta = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d2 if o_type=='call' else -d2)) / 365
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# --- 3. LOGICA PRINCIPAL DE LA APP ---

def main():
    # Carga de datos
    data = fetch_data("COST")
    if not data: return

    # --- SIDEBAR: CONTROL DE VARIABLES ---
    st.sidebar.markdown("## ⚙️ Configuración del Modelo")
    
    # Sliders Protegidos (Clamping)
    p_mercado = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    
    fcf_sug = clamp(data['fcf_last'], 0.0, 50.0)
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 50.0, fcf_sug)
    
    g1_sug = clamp(data['cagr'] * 100, 0.0, 40.0)
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", 0, 40, int(g1_sug)) / 100
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0, 20, 8) / 100
    wacc = st.sidebar.slider("WACC / Descuento (%)", 4.0, 15.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏛️ Datos de Calidad Costco")
    st.sidebar.info(f"Beta: {data['beta']} | P/E: {data['pe']:.1f}x")
    
    if os.path.exists("Guia_Metodologica_COST.pdf"):
        with open("Guia_Metodologica_COST.pdf", "rb") as f:
            st.sidebar.download_button("📄 Guía Institucional", f, "Guia_Metodologica.pdf")

    # Cálculos
    v_fair, flows, pv_f, pv_t = dcf_engine(fcf_in, g1, g2, wacc, 0.025)
    upside = (v_fair / p_mercado - 1) * 100

    # --- UI: DASHBOARD SUPERIOR ---
    st.title(f"🏛️ {data['name']} Intelligence Terminal")
    st.caption(f"Actualizado al {datetime.datetime.now().strftime('%d/%m/%Y')} | Datos en Vivo via SEC EDGAR")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Mercado", f"${p_mercado:.2f}")
    col2.metric("Fair Value DCF", f"${v_fair:.2f}", f"{upside:.1f}%")
    col3.metric("Beta (Riesgo)", f"{data['beta']}", "Low Vol")
    col4.metric("Market Cap", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- TABS DE ANÁLISIS ---
    tabs = st.tabs(["📋 Resumen", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones Lab", "📥 Exportar"])

    # TAB 1: RESUMEN
    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.015, 0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01, 0.03)

        with c1: st.markdown(f'<div class="scenario-card"><span class="label-bajista">BAJISTA</span><div class="metric-costco">${v_baj:.0f}</div><small>Bear Case</small></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="scenario-card"><span class="label-base">CASO BASE</span><div class="metric-costco">${v_fair:.0f}</div><small>Current Assumptions</small></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="scenario-card"><span class="label-alcista">ALCISTA</span><div class="metric-costco">${v_alc:.0f}</div><small>Bull Case</small></div>', unsafe_allow_html=True)
        
        st.markdown("### Composición del Valor Intrínseco")
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_f, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig_donut, use_container_width=True)

    # TAB 2: VALORACIÓN DINÁMICA (BRIDGE)
    with tabs[1]:
        st.subheader("El Puente de Datos: Histórico vs Proyectado")
        hist_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        hist_y = data['fcf_hist'].values[::-1]
        proj_x = [str(int(hist_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=hist_x, y=hist_y, name="Real (10-K)", line=dict(color='#005BAA', width=4), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[hist_x[-1]] + proj_x, y=[hist_y[-1]] + flows, name="Proyección", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", title="Trayectoria del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        

        st.markdown("### Matriz de Sensibilidad: WACC vs g")
        w_range = np.linspace(wacc-0.015, wacc+0.015, 5)
        g_range = np.linspace(0.015, 0.035, 5)
        m = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in g_range] for w in w_range]
        df_m = pd.DataFrame(m, index=[f"W:{x*100:.1f}%" for x in w_range], columns=[f"g:{x*100:.1f}%" for x in g_range])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    # TAB 3: BENCHMARKING
    with tabs[2]:
        peers = pd.DataFrame({
            'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500'],
            'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0, 22.5],
            'Margin': [2.6, 2.4, 3.8, 1.9, 5.1, 11.0]
        })
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='Ticker', y='PE', color='Ticker', title="Multiplo P/E Comparativo", template="plotly_dark"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Margin', y='PE', text='Ticker', size='PE', title="Margen Neto vs Valuación", template="plotly_dark"), use_container_width=True)
        

    # TAB 4: MONTE CARLO
    with tabs[3]:
        st.subheader("Simulación de Escenarios Estocásticos")
        vol = st.slider("Incertidumbre de Pronóstico (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, vol), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob = (np.array(sims) > p_mercado).mean() * 100
        fig_mc = px.histogram(sims, nbins=50, title=f"Probabilidad de Upside: {prob:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mercado, line_color="#f85149", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)
        

    # TAB 5: STRESS TEST
    with tabs[4]:
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        st1, st2 = st.columns(2)
        with st1:
            s_inc = st.slider("Shock Ingreso Real %", -15, 5, 0)
            s_unem = st.slider("Alza Desempleo %", 3, 15, 4)
        with st2:
            s_cpi = st.slider("Inflación CPI %", 0, 12, 3)
            s_wage = st.slider("Alza Salarial %", 0, 10, 4)
        
        adj_g = g1 + (s_inc/200) - (s_unem/500)
        adj_w = wacc + (s_cpi/500) + (s_wage/1000)
        v_s, _, _, _ = dcf_engine(fcf_in, adj_g, g2, adj_w, 0.02)
        st.metric("Valor Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}%")

    # TAB 6: OPCIONES LAB
    with tabs[5]:
        st.subheader("Análisis de Cobertura con Griegas")
        k = st.number_input("Strike Price", value=float(round(p_mercado*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        gr = get_greeks(p_mercado, k, 45/365, 0.045, iv)
        
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Call (45D)", f"${gr['price']:.2f}")
        o2.metric("Delta (Δ)", f"{gr['delta']:.3f}")
        o3.metric("Vega (ν)", f"{gr['vega']:.4f}")
        o4.metric("Theta (θ/día)", f"${gr['theta']:.2f}")
        

    # TAB 7: EXPORTAR
    with tabs[6]:
        st.subheader("Generación de Reporte Institucional")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income_Statement')
            data['bs'].to_excel(wr, sheet_name='Balance_Sheet')
            data['cf'].to_excel(wr, sheet_name='Cash_Flow')
            pd.DataFrame({"Proyeccion_FCF": flows}).to_excel(wr, sheet_name='Projections')
        st.download_button("💾 Descargar Master Excel (3-Statement Model)", buf.getvalue(), f"COST_Institutional_{datetime.date.today()}.xlsx")

if __name__ == "__main__":
    main()
