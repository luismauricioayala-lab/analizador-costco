import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="COST Master Intelligence", layout="wide")

# CSS para Estética de Terminal Financiera
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #e0e0e0; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1c2128; border-radius: 5px; padding: 10px 20px; color: #adbac7; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #238636; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTORES DE CÁLCULO ---
def dcf_engine(fcf, g1, g2, wacc, gt):
    shares, cash = 0.44365, 22.0
    flows = []
    curr = fcf
    for i in range(1, 11):
        curr *= (1 + g1) if i <= 5 else (1 + g2)
        flows.append(curr)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(flows, 1)])
    tv = (flows[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, flows

def black_scholes_extended(S, K, T, r, sigma, type='call'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    theta = -(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d2 if type=='call' else -d2)
    vega = S * norm.pdf(d1) * np.sqrt(T) / 100
    return price, delta, gamma, theta, vega

# --- INTERFAZ ---
st.title("🏛️ Costco Wholesale (COST) - Institutional Intelligence Terminal")

# HEADER METRICS
m1, m2, m3, m4 = st.columns(4)
m1.metric("Market Cap", "$450.2B", "COST-NASDAQ")
m2.metric("P/E TTM", "51.8x", "Premium vs Sector")
m3.metric("Dividend Yield", "0.52%", "Growth Focused")
m4.metric("Membership Rate", "92.4%", "Retention Leader")

st.sidebar.header("🎯 Supuestos Base")
p_actual = st.sidebar.number_input("Precio Mercado ($)", value=950.0)
fcf_base = st.sidebar.number_input("FCF Base ($B)", value=9.5)
wacc_base = st.sidebar.slider("WACC Base (%)", 6.0, 12.0, 8.5) / 100
g_base = st.sidebar.slider("Crecimiento Base (%)", 5, 20, 10) / 100

tabs = st.tabs(["💎 Valoración Pro", "📊 Monte Carlo", "👥 Peer Analysis", "🌪️ Stress Test Lab", "📉 Options Strategy"])

# --- TAB 1: VALORACIÓN ---
with tabs[0]:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Sensibilidad: WACC vs Crecimiento Terminal")
        w_r = np.linspace(wacc_base-0.02, wacc_base+0.02, 5)
        g_r = np.linspace(0.015, 0.035, 5)
        matrix = [[dcf_engine(fcf_base, g_base, g_base*0.7, w, g)[0] for g in g_r] for w in w_r]
        df_s = pd.DataFrame(matrix, index=[f"{x*100:.1f}%" for x in w_r], columns=[f"{x*100:.1f}%" for x in g_r])
        st.plotly_chart(px.imshow(df_s, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with c2:
        fv, _ = dcf_engine(fcf_base, g_base, g_base*0.7, wacc_base, 0.025)
        st.metric("Valor Intrínseco", f"${fv:.2f}", f"{(fv/p_actual-1)*100:.1f}% Upside")
        st.write("El modelo usa un DCF de 2 etapas (años 1-5 y 6-10) con una tasa de salida perpetua del 2.5%.")

# --- TAB 2: MONTE CARLO ---
with tabs[1]:
    st.subheader("Simulación de Probabilidad Monte Carlo")
    n_sims = st.select_slider("Número de simulaciones", options=[100, 500, 1000, 2000], value=1000)
    sims = [dcf_engine(fcf_base, np.random.normal(g_base, 0.02), g_base*0.7, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(n_sims)]
    fig_mc = px.histogram(sims, nbins=50, title="Distribución de Valor Intrínseco", template="plotly_dark", color_discrete_sequence=['#238636'])
    fig_mc.add_vline(x=p_actual, line_color="red", line_dash="dash", annotation_text="Precio Actual")
    st.plotly_chart(fig_mc, use_container_width=True)
    st.write(f"Probabilidad de que el valor justo sea mayor al precio actual: **{(np.array(sims) > p_actual).mean()*100:.1f}%**")

# --- TAB 3: PEER ANALYSIS ---
with tabs[2]:
    peers = pd.DataFrame({
        'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'],
        'P/E': [51.8, 31.2, 17.5, 21.1, 45.0],
        'Growth': [9.5, 6.2, 4.5, 8.2, 12.0],
        'Margin': [2.6, 2.4, 3.8, 1.9, 5.1]
    })
    fig_p = px.scatter(peers, x="Growth", y="P/E", size="Margin", color="Ticker", text="Ticker", template="plotly_dark", title="Valuación Relativa: P/E vs Crecimiento (Tamaño = Margen)")
    st.plotly_chart(fig_p, use_container_width=True)

# --- TAB 4: STRESS TEST LAB ---
with tabs[3]:
    st.header("🌪️ Stress Test Macroeconómico & Operativo")
    st.write("Simula cómo afectan variables granulares a la valoración intrínseca.")
    
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.subheader("Consumo & Ingreso")
        disp_income = st.slider("Ingreso Disponible (%)", -10, 5, 0)
        membership_renewal = st.slider("Renovación Membresías (%)", 80, 100, 92)
    with col_s2:
        st.subheader("Inflación & Costos")
        cpi_impact = st.slider("Inflación (CPI) %", 0, 10, 3)
        wage_growth = st.slider("Crecimiento Salarial (%)", 0, 8, 4)
    with col_s3:
        st.subheader("Mercado")
        unemployment = st.slider("Desempleo (%)", 3, 12, 4)
    
    # Lógica de impacto (Ajuste de variables DCF)
    adj_g = g_base + (disp_income/200) - (unemployment/500) + (membership_renewal-92)/100
    adj_wacc = wacc_base + (cpi_impact/500) + (wage_growth/1000)
    
    val_stress, _ = dcf_engine(fcf_base, adj_g, adj_g*0.7, adj_wacc, 0.025)
    
    st.markdown("---")
    res_c1, res_c2 = st.columns(2)
    res_c1.metric("Valor Post-Estrés", f"${val_stress:.2f}", f"{((val_stress/fv)-1)*100:.1f}% vs Base")
    
    if val_stress < p_actual:
        st.error("🚨 Escenario Crítico: La acción cotiza por encima de su valor en este entorno.")
    else:
        st.success("✅ Resiliencia: Costco mantiene su valor intrínseco incluso bajo presión.")

# --- TAB 5: OPTIONS STRATEGY ---
with tabs[4]:
    st.header("📉 Options Strategy Lab")
    
    o1, o2 = st.columns([1, 2])
    with o1:
        st.subheader("Configuración del Contrato")
        op_type = st.radio("Tipo de Opción", ["Call", "Put"])
        k_strike = st.number_input("Precio Strike ($)", value=float(round(p_actual*1.05, 0)))
        t_days = st.slider("Días al Vencimiento", 1, 365, 30)
        iv = st.slider("Volatilidad Implícita (IV %)", 10, 100, 25) / 100
        risk_free = 0.045
        
        # Calcular Black-Scholes
        price, delta, gamma, theta, vega = black_scholes_extended(p_actual, k_strike, t_days/365, risk_free, iv, op_type.lower())
        
        st.markdown("---")
        st.subheader("Las Griegas")
        g_c1, g_c2 = st.columns(2)
        g_c1.write(f"**Delta:** {delta:.3f}")
        g_c1.write(f"**Gamma:** {gamma:.4f}")
        g_c2.write(f"**Theta:** {theta:.3f}")
        g_c2.write(f"**Vega:** {vega:.3f}")

    with o2:
        st.subheader("Perfil de Payoff (P&L)")
        x_range = np.linspace(p_actual*0.7, p_actual*1.3, 100)
        if op_type == "Call":
            y_payoff = np.maximum(x_range - k_strike, 0) - price
        else:
            y_payoff = np.maximum(k_strike - x_range, 0) - price
            
        fig_opt = go.Figure()
        fig_opt.add_trace(go.Scatter(x=x_range, y=y_payoff, fill='tozeroy', name='Payoff', line=dict(color='#238636')))
        fig_opt.add_hline(y=0, line_dash="dash", line_color="white")
        fig_opt.update_layout(template="plotly_dark", xaxis_title="Precio de COST al Vencimiento", yaxis_title="Ganancia / Pérdida ($)")
        st.plotly_chart(fig_opt, use_container_width=True)
        
        st.metric("Precio del Contrato (Prima)", f"${price:.2f}")

if __name__ == "__main__":
    main()