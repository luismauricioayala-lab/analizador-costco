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

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILO PROFESIONAL ---
st.set_page_config(
    page_title="COST Institutional | Bloomberg Mode",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de CSS Avanzado: Look & Feel de Terminal Financiera
st.markdown("""
    <style>
    /* Fondo y contenedores */
    .main { background-color: #0b0e14; color: #e6edf3; }
    [data-testid="stHeader"] { background: rgba(11, 14, 20, 0.8); }
    
    /* Sidebar Estilo Dark Pro */
    [data-testid="stSidebar"] { 
        background-color: #161b22; 
        border-right: 1px solid #30363d; 
    }
    
    /* Tarjetas de Métricas (Glassmorphism) */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border: 1px solid #005BAA;
    }

    /* Escenarios: Estilo Cards Bloomberg */
    .scenario-card {
        background: #1c2128;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #30363d;
        text-align: center;
        margin-bottom: 10px;
    }
    .price-large { font-size: 38px; font-weight: 800; color: #ffffff; margin: 5px 0; }
    
    /* Badges de Estado */
    .badge-red { color: #f85149; background: rgba(248, 81, 73, 0.1); padding: 5px 12px; border-radius: 15px; font-weight: bold; font-size: 12px; }
    .badge-orange { color: #dbab09; background: rgba(219, 171, 9, 0.1); padding: 5px 12px; border-radius: 15px; font-weight: bold; font-size: 12px; }
    .badge-green { color: #3fb950; background: rgba(63, 185, 80, 0.1); padding: 5px 12px; border-radius: 15px; font-weight: bold; font-size: 12px; }

    /* Custom Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #161b22;
        border-radius: 6px;
        color: #8b949e;
        border: 1px solid #30363d;
        padding: 0 20px;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #005BAA !important; 
        color: white !important; 
        border: 1px solid #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES DE CÁLCULO Y SEGURIDAD ---

def clamp(v, mn, mx): 
    return float(np.clip(v, mn, mx))

@st.cache_data(ttl=3600)
def load_data(ticker):
    try:
        t = yf.Ticker(ticker)
        inf, cf = t.info, t.cashflow
        fcf = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']) / 1e9
        vals = fcf.values[::-1]
        cagr = (vals[-1]/vals[0])**(1/(len(vals)-1))-1 if len(vals)>1 else 0.12
        return {
            "name": inf.get('longName', 'Costco Wholesale'),
            "price": inf.get('currentPrice', 950.0),
            "beta": inf.get('beta', 0.79),
            "fcf_last": fcf.iloc[0],
            "fcf_hist": fcf,
            "cagr": cagr,
            "pe": inf.get('trailingPE', 51.8),
            "mkt_cap": inf.get('marketCap', 450e9)/1e9,
            "is": t.financials, "bs": t.balance_sheet, "cf": cf
        }
    except: return None

def dcf_model(fcf, g1, g2, wacc, gt=0.025, shares=0.443, cash=22.0):
    projs = []
    curr = fcf
    for i in range(1, 11):
        curr *= (1 + g1) if i <= 5 else (1 + g2)
        projs.append(curr)
    pv_f = sum([f/(1+wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1]*(1+gt))/(wacc-gt)
    pv_t = tv/(1+wacc)**10
    return ((pv_f + pv_t)/shares)+cash, projs, pv_f, pv_t

def greeks_engine(S, K, T, r, sigma, o_type='call'):
    T = max(T, 0.0001)
    d1 = (np.log(S/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if o_type == 'call':
        p = S*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d2)
        d = norm.cdf(d1)
    else:
        p = K*np.exp(-r*T)*norm.cdf(-d2)-S*norm.cdf(-d1)
        d = norm.cdf(d1)-1
    return {"p": p, "d": d, "v": (S*np.sqrt(T)*norm.pdf(d1))/100, "t": (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T)))-r*K*np.exp(-r*T)*norm.cdf(d1))/365}

# --- 3. UI: CONSTRUCCIÓN DE LA TERMINAL ---

def main():
    with st.spinner("⚡ Cargando Inteligencia de Mercado..."):
        data = load_data("COST")
        if not data: return

    # --- SIDEBAR UI ---
    st.sidebar.markdown("## 📟 Panel de Control")
    st.sidebar.markdown("---")
    
    # Inputs con Clamping para evitar crashes
    p_mkt = st.sidebar.number_input("Precio Spot ($)", value=float(data['price']))
    
    fcf_init = clamp(data['fcf_last'], 0.0, 60.0)
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 60.0, fcf_init)
    
    g_init = clamp(data['cagr']*100, 0.0, 50.0)
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", 0, 50, int(g_init)) / 100
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0, 25, 8) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 4.0, 16.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Quick Stats")
    st.sidebar.write(f"**Beta:** {data['beta']} (Baja Vol)")
    st.sidebar.write(f"**P/E TTM:** {data['pe']:.1f}x")
    
    if os.path.exists("Guia.pdf"):
        with open("Guia.pdf", "rb") as f:
            st.sidebar.download_button("📂 Descargar Reporte PDF", f, "Institutional_Guide.pdf")

    # Cálculos Core
    v_fair, flows, pv_f, pv_t = dcf_model(fcf_in, g1, g2, wacc)
    upside = (v_fair/p_mkt - 1) * 100

    # --- MAIN UI: DASHBOARD ---
    st.title(f"🏛️ {data['name']} Intelligence")
    st.markdown(f"**Terminal ID:** COST-US-2026 | **Status:** Conectado a SEC EDGAR")
    
    # Grid de Métricas Principales
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("PRECIO SPOT", f"${p_mkt:.2f}")
    m2.metric("FAIR VALUE (DCF)", f"${v_fair:.2f}", f"{upside:.1f}%")
    m3.metric("BETA INSTITUCIONAL", f"{data['beta']}", "Defensivo")
    m4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- TABS DE ANÁLISIS ---
    t = st.tabs(["📋 Executive Summary", "💎 DCF Analysis", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📥 Data"])

    with t[0]: # SUMMARY
        st.subheader("Simulación de Escenarios de Inversión")
        c1, c2, c3 = st.columns(3)
        # Escenarios
        v_baj, _, _, _ = dcf_model(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_model(fcf_in, g1+0.04, g2+0.02, wacc-0.01)

        c1.markdown(f'<div class="scenario-card"><span class="badge-red">BEAR CASE</span><div class="price-large">${v_baj:.0f}</div><small>Shock en Margen / Tasas +200bps</small></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="scenario-card"><span class="badge-orange">BASE CASE</span><div class="price-large">${v_fair:.0f}</div><small>Continuidad Operativa Actual</small></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="scenario-card"><span class="badge-green">BULL CASE</span><div class="price-large">${v_alc:.0f}</div><small>Expansión Asia / Membresía +15%</small></div>', unsafe_allow_html=True)
        
        # Donut de Composición
        fig_donut = go.Figure(data=[go.Pie(labels=['Caja 1-10Y', 'Valor Perpetuo'], values=[pv_f, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=450, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_donut, use_container_width=True)

    with t[1]: # DCF BRIDGE
        st.subheader("Trayectoria de Flujo de Caja Libre ($B)")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1])+i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (SEC)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", hovermode="x unified", height=500)
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        # Sensibilidad
        st.markdown("### Matriz de Sensibilidad: WACC vs g")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_model(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"{x*100:.1f}%" for x in wr], columns=[f"{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with t[2]: # BENCHMARKING
        peers = pd.DataFrame({'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0], 'Yield': [12.4, 6.2, 4.5, 8.2, 10.5]})
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='Ticker', y='PE', color='Ticker', title="Múltiplo P/E Comparativo", template="plotly_dark"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Yield', y='PE', text='Ticker', size='PE', title="Crecimiento vs Valuación", template="plotly_dark"), use_container_width=True)

    with t[3]: # MONTE CARLO
        st.subheader("Distribución de Probabilidades Monte Carlo")
        vol = st.slider("Incertidumbre de Pronóstico (%)", 1, 10, 3) / 100
        sims = [dcf_model(fcf_in, np.random.normal(g1, vol), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {(np.array(sims)>p_mkt).mean()*100:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="#f85149", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)

    with t[4]: # STRESS TEST
        st.subheader("🌪️ Laboratorio de Stress Macroeconómico")
        s1, s2 = st.columns(2)
        with s1: 
            sh_i = st.slider("Shock Ingreso Disponible %", -20, 10, 0)
            sh_u = st.slider("Alza Desempleo %", 3, 18, 4)
        with s2:
            sh_c = st.slider("Inflación CPI %", 0, 15, 3)
            sh_w = st.slider("Carga Salarial %", 0, 12, 4)
        v_s, _, _, _ = dcf_model(fcf_in, g1+(sh_i/200)-(sh_u/500), g2, wacc+(sh_c/500)+(sh_w/1000))
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}%")

    with t[5]: # OPTIONS
        st.subheader("Análisis de Griegas y Cobertura")
        k = st.number_input("Precio Strike", value=float(round(p_mkt*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        grk = greeks_engine(p_mkt, k, 45/365, 0.045, iv)
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Estimada", f"${grk['p']:.2f}"); o2.metric("Delta (Δ)", f"{grk['d']:.3f}")
        o3.metric("Vega (ν)", f"{grk['v']:.4f}"); o4.metric("Theta (θ/día)", f"${grk['t']:.2f}")

    with t[6]: # DATA
        st.subheader("Exportación de Estados Financieros")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income_Statement')
            data['bs'].to_excel(wr, sheet_name='Balance_Sheet')
            data['cf'].to_excel(wr, sheet_name='Cash_Flow')
        st.download_button("💾 Descargar Master Excel (3-Statement)", buf.getvalue(), f"COST_Institutional_{datetime.date.today()}.xlsx")

if __name__ == "__main__":
    main()
