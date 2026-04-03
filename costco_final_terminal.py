import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.1); }
    [data-testid="stMetricValue"] { font-size: 26px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES MATEMÁTICOS ---
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

def calculate_full_greeks(S, K, T, r, sigma, type='call'):
    T = max(T, 0.0001) 
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        rho = K * T * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)
        
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    theta = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d2 if type=='call' else -d2)) / 365
    
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho / 100}

# --- 3. INTERFAZ ---
def main():
    st.title("🏛️ COST Institutional Intelligence Hub")
    
    # SIDEBAR
    st.sidebar.header("🎯 Supuestos del Analista")
    p_mercado = st.sidebar.number_input("Precio Spot COST ($)", value=950.0)
    fcf_base = st.sidebar.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
    wacc_base = st.sidebar.slider("WACC Base (%)", 5.0, 15.0, 8.5) / 100
    g_base = st.sidebar.slider("Crecimiento A1-5 (%)", 5, 20, 12) / 100

    # HEADER METRICS
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Market Cap", "$450.2B", "NASDAQ: COST")
    h2.metric("P/E TTM", "51.8x", "Premium vs Sector")
    h3.metric("FCF Yield", "2.1%", "Sano")
    h4.metric("Beta", "0.79", "Defensivo")

    st.markdown("---")
    tabs = st.tabs(["💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Options Strategy Lab"])

    # --- TAB 1: VALORACIÓN ---
    with tabs[0]:
        fv, flows = dcf_engine(fcf_base, g_base, g_base*0.7, wacc_base, 0.025)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Matriz de Sensibilidad: WACC vs G Terminal")
            w_r = np.linspace(wacc_base-0.02, wacc_base+0.02, 5)
            g_r = np.linspace(0.015, 0.035, 5)
            matrix = [[dcf_engine(fcf_base, g_base, g_base*0.7, w, g)[0] for g in g_r] for w in w_r]
            df_s = pd.DataFrame(matrix, index=[f"{x*100:.1f}%" for x in w_r], columns=[f"{x*100:.1f}%" for x in g_r])
            st.plotly_chart(px.imshow(df_s, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_white"), use_container_width=True)
        with c2:
            st.metric("Valor Intrínseco", f"${fv:.2f}", f"{(fv/p_mercado-1)*100:.1f}% Upside")
            st.write("**Flujos Proyectados:**")
            st.bar_chart(flows)

    # --- TAB 2: BENCHMARKING ---
    with tabs[1]:
        st.subheader("Análisis de Peers y Mercado")
        idx = st.selectbox("Benchmark:", ["S&P 500", "NASDAQ 100", "Dow Jones"])
        pe_bench = {"S&P 500": 22.5, "NASDAQ 100": 29.2, "Dow Jones": 19.5}[idx]
        
        peers = pd.DataFrame({
            'Ticker': ['COST', 'WMT', 'TGT', 'BJ', idx],
            'P/E': [51.8, 31.2, 17.5, 21.1, pe_bench],
            'Growth': [9.5, 6.2, 4.5, 8.2, 7.5]
        })
        
        cb1, cb2 = st.columns(2)
        with cb1: st.plotly_chart(px.bar(peers, x='Ticker', y='P/E', color='Ticker', template="plotly_white"), use_container_width=True)
        with cb2: st.plotly_chart(px.scatter(peers, x='Growth', y='P/E', text='Ticker', size='P/E', color='Ticker', template="plotly_white"), use_container_width=True)

    # --- TAB 3: MONTE CARLO ---
    with tabs[2]:
        st.subheader("Simulación Monte Carlo (1,000 Escenarios)")
        vol_mc = st.slider("Volatilidad de Pronóstico", 0.01, 0.05, 0.02)
        sims = [dcf_engine(fcf_base, np.random.normal(g_base, vol_mc), g_base*0.7, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_mercado).mean() * 100
        
        fig_mc = px.histogram(sims, nbins=40, title=f"Probabilidad de Éxito: {prob_success:.1f}%", template="plotly_white", color_discrete_sequence=['#27ae60'])
        fig_mc.add_vline(x=p_mercado, line_color="red", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)

    # --- TAB 4: STRESS TEST ---
    with tabs[3]:
        st.header("🌪️ Stress Test Lab")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            income_drop = st.slider("Ingreso Disponible %", -10, 5, 0)
            unemp_hike = st.slider("Desempleo %", 3, 12, 4)
        with sc2:
            inf_cpi = st.slider("Inflación (CPI) %", 0, 10, 3)
            wage_press = st.slider("Costo Laboral %", 0, 8, 4)
        with sc3:
            black_swan = st.checkbox("Crisis Geopolítica")

        adj_g = g_base + (income_drop/200) - (unemp_hike/500) - (0.04 if black_swan else 0)
        adj_wacc = wacc_base + (inf_cpi/500) + (wage_press/1000)
        v_stress, _ = dcf_engine(fcf_base, adj_g, adj_g*0.7, adj_wacc, 0.025)
        st.metric("Valor Post-Estrés", f"${v_stress:.2f}", f"{((v_stress/fv)-1)*100:.1f}% vs Base")

    # --- TAB 5: OPCIONES & GRIEGAS ---
    with tabs[4]:
        st.header("🔬 Deep Options Analysis")
        o_c1, o_c2 = st.columns([1, 2])
        with o_c1:
            o_type = st.radio("Tipo", ["Call", "Put"])
            strike = st.number_input("Strike Price ($)", value=float(round(p_mercado * 1.05, 0)))
            days = st.slider("Días al Vencimiento", 1, 365, 30)
            sigma = st.slider("Volatilidad Implícita (IV %)", 5, 100, 25) / 100
            
            res = calculate_full_greeks(p_mercado, strike, days/365, 0.045, sigma, o_type.lower())
            
            st.metric("Precio del Contrato", f"${res['price']:.2f}")
            st.markdown("---")
            st.subheader("Griegas")
            st.write(f"**Delta:** {res['delta']:.3f} (Sensibilidad Precio)")
            st.write(f"**Gamma:** {res['gamma']:.4f} (Aceleración Delta)")
            st.write(f"**Vega:** {res['vega']:.3f} (Sensibilidad IV)")
            st.write(f"**Theta (Día):** ${res['theta']:.2f} (Decaimiento Temporal)")
            st.write(f"**Rho:** {res['rho']:.3f} (Sensibilidad Tasas)")
            
        with o_c2:
            st.subheader("Curva de Sensibilidad Delta")
            x_range = np.linspace(p_mercado*0.8, p_mercado*1.2, 50)
            deltas = [calculate_full_greeks(x, strike, days/365, 0.045, sigma, o_type.lower())['delta'] for x in x_range]
            fig_delta = px.line(x=x_range, y=deltas, labels={'x': 'Precio COST', 'y': 'Delta'}, template="plotly_white")
            st.plotly_chart(fig_delta, use_container_width=True)

if __name__ == "__main__":
    main()