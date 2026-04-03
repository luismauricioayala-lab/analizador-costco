import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="COST Institutional Master", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f9f9f9; color: #1e1e1e; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f3f5; border-radius: 5px; padding: 10px 15px; font-weight: bold; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTORES DE CÁLCULO ---
def dcf_engine(fcf_base, g1, g2, wacc, gt, shares=0.44365, cash=22.0):
    fcf = []
    curr = fcf_base
    for i in range(1, 11):
        curr *= (1 + g1) if i <= 5 else (1 + g2)
        fcf.append(curr)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(fcf, 1)])
    tv = (fcf[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, fcf, pv_f, pv_t

# --- HEADER: MÉTRICAS CLAVE ---
st.title("Costco Wholesale (COST) — Terminal Institucional")
st.caption("Intelligence Hub v5.0 • Valuación Fundamental, Macro & Derivados")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Market Cap", "$450.2B", "443.65M Shares")
m2.metric("P/E TTM", "51.8x", "Sector Avg: 25.4x")
m3.metric("EV/EBITDA", "32.4x", "EBITDA: $13.5B")
m4.metric("FCF Yield", "2.1%", "FY2025 Est.")

st.markdown("---")

# --- SIDEBAR: SUPUESTOS Y CONTROLES ---
st.sidebar.header("🕹️ Supuestos de Valuación")
precio_actual = st.sidebar.number_input("Precio Mercado ($)", value=1000.0)
fcf_in = st.sidebar.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
g1 = st.sidebar.slider("Crecimiento Años 1-5 (%)", 1, 25, 10) / 100
g2 = st.sidebar.slider("Crecimiento Años 6-10 (%)", 1, 20, 7) / 100
wacc = st.sidebar.slider("WACC (%)", 5.0, 15.0, 9.0) / 100
gt = st.sidebar.slider("Crecimiento Terminal (%)", 0.5, 5.0, 2.5) / 100

st.sidebar.markdown("---")
st.sidebar.header("🌍 Variables Macro")
pib = st.sidebar.slider("Crecimiento PIB (%)", -5.0, 5.0, 2.1)
desempleo = st.sidebar.slider("Desempleo (%)", 3.0, 12.0, 4.2)
swan_risk = 0
if st.sidebar.checkbox("Black Swan: Crisis Logística"): swan_risk += 0.03
if st.sidebar.checkbox("Black Swan: Ciberataque"): swan_risk += 0.02

# --- AJUSTES DINÁMICOS POR MACRO ---
adj_wacc = wacc + (abs(min(0, pib))/50) + swan_risk
adj_g1 = g1 + (pib/150) - (desempleo/300)

# --- NAVEGACIÓN ---
tabs = st.tabs(["💎 DCF & Sensibilidad", "📊 Monte Carlo", "👥 Peers & Market", "🌪️ Stress Test", "📉 Options"])

# --- TAB 1: VALORACIÓN E IMAGEN ---
with tabs[0]:
    fair_v, flows, pv_f, pv_t = dcf_engine(fcf_in, adj_g1, g2, adj_wacc, gt)
    c1, c2 = st.columns([1.5, 1])
    
    with c1:
        st.subheader("Proyección FCF 10 Años")
        fig_f = go.Figure(data=[go.Bar(x=[f"A{i}" for i in range(1,11)], y=flows, marker_color='#007bff')])
        fig_f.update_layout(height=350, template="plotly_white")
        st.plotly_chart(fig_f, use_container_width=True)
        
        st.subheader("Matriz de Sensibilidad (WACC vs g)")
        w_s = np.linspace(adj_wacc-0.02, adj_wacc+0.02, 5)
        g_s = np.linspace(gt-0.01, gt+0.01, 5)
        matrix = [[dcf_engine(fcf_in, adj_g1, g2, w, g)[0] for g in g_s] for w in w_s]
        df_s = pd.DataFrame(matrix, index=[f"{w*100:.1f}%" for w in w_s], columns=[f"{g*100:.1f}%" for g in g_s])
        st.plotly_chart(px.imshow(df_s, text_auto='.0f', color_continuous_scale='RdYlGn'), use_container_width=True)

    with c2:
        st.subheader("Fair Value")
        upside = (fair_v/precio_actual - 1)*100
        st.markdown(f"<h1 style='text-align: center;'>${fair_v:.0f}</h1>", unsafe_allow_html=True)
        st.metric("Margen de Seguridad", f"{upside:.1f}%", delta_color="inverse" if upside < 0 else "normal")
        st.markdown(f"**PV Flujos:** ${pv_f:.1f}B | **PV Terminal:** ${pv_t:.1f}B")
        st.markdown("---")
        st.write("**Escenarios Rápidos**")
        st.success(f"Alcista: ${dcf_engine(fcf_in, adj_g1+0.03, g2, adj_wacc-0.01, gt+0.005)[0]:.0f}")
        st.error(f"Bajista: ${dcf_engine(fcf_in, adj_g1-0.04, g2-0.02, adj_wacc+0.02, gt-0.01)[0]:.0f}")

# --- TAB 2: MONTE CARLO ---
with tabs[1]:
    st.header("Simulación de Probabilidad Monte Carlo")
    st.write("Calculando 1,000 escenarios aleatorios basados en volatilidad de supuestos...")
    sims = [dcf_engine(fcf_in, np.random.normal(adj_g1, 0.02), g2, np.random.normal(adj_wacc, 0.01), gt)[0] for _ in range(1000)]
    fig_mc = px.histogram(sims, nbins=50, title="Distribución de Valor Intrínseco", template="plotly_white", color_discrete_sequence=['#28a745'])
    fig_mc.add_vline(x=precio_actual, line_color="red", line_dash="dash", annotation_text="Precio Actual")
    st.plotly_chart(fig_mc, use_container_width=True)

# --- TAB 3: PEERS ---
with tabs[2]:
    st.header("Análisis Comparativo Seleccionable")
    market = st.selectbox("Benchmark de Mercado", ["S&P 500", "NASDAQ 100", "Dow Jones"])
    peers = st.multiselect("Pares a Comparar", ["WMT", "TGT", "BJ", "TESCO", "AMZN"], default=["WMT", "TGT"])
    
    peer_db = {'COST': [51.8, 9.5], 'WMT': [31.2, 6.2], 'TGT': [17.5, 4.5], 'BJ': [21.1, 8.2], 'TESCO': [14.5, 3.1], 'AMZN': [45.0, 12.0]}
    df_p = pd.DataFrame([{'Ticker': k, 'PE': v[0], 'Growth': v[1]} for k, v in peer_db.items() if k in ['COST'] + peers])
    
    fig_p = px.scatter(df_p, x="Growth", y="PE", text="Ticker", size="PE", color="Ticker", title="Valuación Relativa", template="plotly_white")
    st.plotly_chart(fig_p, use_container_width=True)

# --- TAB 4: STRESS TEST ---
with tabs[3]:
    st.header("Stress Test Macroeconómico")
    st.write(f"Veredicto bajo entorno de PIB {pib}% y Desempleo {desempleo}%")
    impacto = ((fair_v / dcf_engine(fcf_in, g1, g2, wacc, gt)[0]) - 1) * 100
    st.metric("Degradación de Valor por Macro", f"{impacto:.2f}%")
    if impacto < -20: st.error("🚨 ALERTA: La tesis de inversión se rompe bajo este escenario macro.")
    else: st.success("✅ RESILIENCIA: El modelo de Costco absorbe el impacto macro.")

# --- TAB 5: OPTIONS ---
with tabs[4]:
    st.header("Options Master (Black-Scholes)")
    col_o1, col_o2 = st.columns(2)
    with col_o1:
        strike = st.number_input("Strike", value=float(np.round(precio_actual*1.05, 0)))
        vol = st.slider("Volatilidad Implícita (%)", 10, 100, 30) / 100
    
    T = 30/365
    d1 = (np.log(precio_actual/strike) + (0.05 + 0.5*vol**2)*T) / (vol*np.sqrt(T))
    call_p = precio_actual * norm.cdf(d1) - strike * np.exp(-0.05*T) * norm.cdf(d1 - vol*np.sqrt(T))
    
    with col_o2:
        st.metric("Precio Teórico Call (30d)", f"${call_p:.2f}")
        st.metric("Delta (Probabilidad ITM)", f"{norm.cdf(d1)*100:.1f}%")