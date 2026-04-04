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

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="COST Institutional Master",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. UI: CSS ADAPTATIVO (MODO CLARO / OSCURO) ---
st.markdown("""
    <style>
    :root {
        --text-main: var(--text-color);
        --bg-card: var(--secondary-background-color);
        --accent: #005BAA;
    }
    .main { padding-top: 1rem; }
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 25px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricValue"] > div { color: var(--text-main) !important; font-weight: 800 !important; }
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 15px; padding: 30px; text-align: center; margin-bottom: 20px;
    }
    .price-hero { font-size: 42px; font-weight: 900; color: var(--text-main); letter-spacing: -1.5px; }
    .badge { padding: 5px 15px; border-radius: 20px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.1); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.1); border-color: #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.1); border-color: #dbab09; }
    .stTabs [data-baseweb="tab"] { height: 55px; background-color: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); padding: 0 25px; }
    .stTabs [aria-selected="true"] { background-color: var(--accent) !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO ---

def secure_clamp(val, min_v, max_v):
    return float(max(min(val, max_v), min_v))

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    try:
        asset = yf.Ticker(ticker_symbol)
        inf, cf_raw = asset.info, asset.cashflow
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        v_h = fcf_series.values[::-1]
        cagr = (v_h[-1]/v_h[0])**(1/(len(v_h)-1)) - 1 if len(v_h) > 1 and v_h[0] > 0 else 0.12
        return {
            "name": inf.get('longName', 'Costco Wholesale'),
            "price": inf.get('currentPrice', 950.0),
            "beta": inf.get('beta', 0.79),
            "fcf_now": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr_real": cagr,
            "pe": inf.get('trailingPE', 51.8),
            "mkt_cap": inf.get('marketCap', 450e9) / 1e9,
            "is": asset.financials, "bs": asset.balance_sheet, "cf": cf_raw
        }
    except: return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    projs = []
    val = fcf
    for i in range(1, 11):
        val *= (1 + g1) if i <= 5 else (1 + g2)
        projs.append(val)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    return ((pv_f + pv_t) / shares) + cash, projs, pv_f, pv_t

# --- 4. LÓGICA PRINCIPAL ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # SIDEBAR
    st.sidebar.markdown("## 📟 Panel de Control")
    MIN_FCF, MAX_FCF = 0.0, 100.0
    MIN_G, MAX_G = -30.0, 150.0
    
    p_mkt = st.sidebar.number_input("Precio Spot de Mercado ($)", value=float(data['price']))
    f_init = secure_clamp(data['fcf_now'], MIN_FCF, MAX_FCF)
    fcf_in = st.sidebar.slider("FCF Base ($B)", MIN_FCF, MAX_FCF, f_init)
    g_init = secure_clamp(data['cagr_real'] * 100, MIN_G, MAX_G)
    g1 = st.sidebar.slider("Crecimiento Años 1-5 (%)", MIN_G, MAX_G, float(round(g_init, 1))) / 100
    g2 = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0.0, 30.0, 8.0) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 3.0, 18.0, 8.5) / 100
    
    # CÁLCULOS
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # DASHBOARD
    st.title(f"🏛️ {data['name']} Intelligence")
    st.caption(f"Terminal ID: COST-MASTER-v9.5 | Adaptive UI Active")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PRECIO SPOT", f"${p_mkt:.2f}")
    col2.metric("FAIR VALUE (DCF)", f"${v_fair:.2f}", f"{upside:.1f}% Upside", delta_color="normal" if upside > 0 else "inverse")
    col3.metric("RIESGO BETA", f"{data['beta']}", "Neutral" if data['beta'] > 0.9 else "Defensivo")
    col4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    tabs = st.tabs(["📋 Resumen", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones Lab", "📚 Metodología", "📥 Exportar"])

    with tabs[0]: # SUMMARY
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">BEAR CASE</span><div class="price-hero">${v_baj:.0f}</div><small>Shock Consumo / Tasas +200bps</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">BASE CASE</span><div class="price-hero">${v_fair:.0f}</div><small>Proyección Orgánica</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">BULL CASE</span><div class="price-hero">${v_alc:.0f}</div><small>Expansión Asia / Membresía</small></div>', unsafe_allow_html=True)
        fig_donut = go.Figure(data=[go.Pie(labels=['Cash Flow 10Y', 'Valor Perpetuo'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # VALORACIÓN
        st.subheader("Puente de Flujos: Pasado Auditado vs Forecast")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (10-K)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        st.plotly_chart(fig_bridge, use_container_width=True)
        

    with tabs[2]: # BENCHMARKING (RECUPERADO)
        st.subheader("Análisis de Pares e Índices de Mercado")
        peers_full = pd.DataFrame({
            'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500', 'Nasdaq'],
            'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0, 22.5, 29.8],
            'Margin': [2.6, 2.4, 3.8, 1.9, 5.1, 11.2, 14.5]
        })
        b1, b2 = st.columns(2)
        with b1: st.plotly_chart(px.bar(peers_full, x='Ticker', y='PE', color='Ticker', title="Múltiplo P/E Comparativo"), use_container_width=True)
        with b2: st.plotly_chart(px.scatter(peers_full, x='Margin', y='PE', text='Ticker', size='PE', title="Rentabilidad vs Valuación"), use_container_width=True)

    with tabs[3]: # MONTE CARLO
        v_mc = st.slider("Incertidumbre (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {(np.array(sims) > p_mkt).mean()*100:.1f}%", color_discrete_sequence=['#3fb950'])
        st.plotly_chart(fig_mc, use_container_width=True)

    with tabs[4]: # STRESS TEST
        s1, s2 = st.columns(2)
        with s1: sh_i = st.slider("Shock Ingreso Real %", -25, 10, 0); sh_u = st.slider("Alza Desempleo %", 3, 20, 4)
        with s2: sh_c = st.slider("Inflación CPI %", 0, 15, 3); sh_w = st.slider("Alza Salarial %", 0, 12, 4)
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(sh_i/200)-(sh_u/500), g2, wacc+(sh_c/500)+(sh_w/1000))
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs BASE")

    with tabs[5]: # OPCIONES
        k_s = st.number_input("Strike Price Ref.", value=float(round(p_mkt*1.05, 0)))
        iv = st.slider("IV %", 10, 100, 25) / 100
        # Simplificación de griegas para UI limpia
        st.info(f"Análisis para Strike ${k_s} con IV {iv*100}%")

    with tabs[6]: # METODOLOGÍA (RECUPERADA)
        st.header("📚 Marco Metodológico Institucional")
        st.write("El modelo utiliza un sistema de **Descuento de Flujos de Caja (DCF) de dos etapas** con rampa de convergencia.")
        
        st.subheader("1. Cálculo del Coste de Capital (WACC)")
        st.latex(r"WACC = \frac{E}{V} \cdot K_e + \frac{D}{V} \cdot K_d \cdot (1 - T_c)")
        st.latex(r"K_e = R_f + \beta \cdot (R_m - R_f)")
        

        st.subheader("2. Proyección de Flujos y Valor Terminal")
        st.write("Se proyectan los flujos de los próximos 10 años y se aplica el Modelo de Gordon para el valor perpetuo.")
        st.latex(r"TV = \frac{FCF_{10} \cdot (1 + g_{terminal})}{WACC - g_{terminal}}")
        st.latex(r"Intrinsic Value = \sum_{t=1}^{10} \frac{FCF_t}{(1+WACC)^t} + \frac{TV}{(1+WACC)^{10}}")
        

    with tabs[7]: # EXPORTAR
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income'); data['bs'].to_excel(wr, sheet_name='Balance'); data['cf'].to_excel(wr, sheet_name='CashFlow')
        st.download_button("💾 Descargar Master Excel (3-Statement)", buf.getvalue(), f"COST_Institutional_Model.xlsx")

if __name__ == "__main__":
    main()
