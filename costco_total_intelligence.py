import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.1); }
    .scenario-card { background-color: white; border-radius: 15px; padding: 20px; border: 1px solid #e0e0e0; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); color: #1c1c1c; }
    .metric-costco { color: #1c1c1c; font-size: 32px; font-weight: bold; margin: 5px 0; }
    .label-bajista { color: #d93025; background-color: #fce8e6; padding: 2px 10px; border-radius: 10px; font-weight: bold; }
    .label-base { color: #f29900; background-color: #fff4e5; padding: 2px 10px; border-radius: 10px; font-weight: bold; }
    .label-alcista { color: #188038; background-color: #e6f4ea; padding: 2px 10px; border-radius: 10px; font-weight: bold; }
    .educational-box { background-color: rgba(35, 134, 54, 0.05); padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES FINANCIEROS ---
def dcf_engine(fcf, g1, g2, wacc, gt, shares=0.44365, cash=22.0):
    flows = []
    curr = fcf
    for i in range(1, 11):
        curr *= (1 + g1) if i <= 5 else (1 + g2)
        flows.append(curr)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(flows, 1)])
    tv = (flows[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, flows, pv_f, pv_t

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

# --- 3. DATOS DE MERCADO ---
PEERS_DATA = pd.DataFrame({
    'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500', 'NASDAQ'],
    'PE': [52.4, 31.2, 17.5, 21.1, 45.0, 22.5, 29.2],
    'Rev_Growth': [9.5, 6.2, 4.5, 8.2, 12.5, 7.0, 11.0],
    'Margin': [2.6, 2.4, 3.8, 1.9, 5.1, 11.0, 15.0]
})

# --- 4. INTERFAZ PRINCIPAL ---
def main():
    st.title("🏛️ Costco Wholesale (COST) — Institutional Master Terminal")
    st.caption("v9.0 Build 2026 • High-Density Financial Analysis Hub")

    # --- SIDEBAR: TODOS LOS INPUTS ---
    st.sidebar.header("🎯 Supuestos del Analista")
    p_actual = st.sidebar.number_input("Precio Mercado ($)", value=950.0)
    
    with st.sidebar.expander("📈 Parámetros DCF", expanded=True):
        fcf_in = st.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
        g1 = st.slider("Crecimiento Años 1-5 (%)", 1, 20, 12) / 100
        g2 = st.slider("Crecimiento Años 6-10 (%)", 1, 15, 8) / 100
        wacc_base = st.slider("WACC Base (%)", 5.0, 15.0, 8.5) / 100
        gt = 0.025 # Crecimiento Terminal

    with st.sidebar.expander("🌪️ Variables de Stress Test"):
        disposable_inc = st.slider("Ingreso Disponible %", -10, 5, 0)
        unemployment = st.slider("Desempleo %", 3, 15, 4)
        cpi = st.slider("Inflación (CPI) %", 0, 10, 3)
        wage_press = st.slider("Alza Salarial %", 0, 8, 4)

    # HEADER METRICS
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("P/E TTM", "52.4x", "Premium")
    h2.metric("Market Cap", "$450.2B", "COST-NASDAQ")
    h3.metric("Beta", "0.79", "Defensivo")
    h4.metric("Retention", "92.4%", "Gold Standard")

    st.markdown("---")
    tabs = st.tabs(["📋 Resumen Ejecutivo", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Opciones Lab", "📚 Metodología Masterclass"])

    # --- TAB 0: RESUMEN EJECUTIVO (ESTILO IMAGEN) ---
    with tabs[0]:
        c_esc1, c_esc2, c_esc3 = st.columns(3)
        # Bajista
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.5, g2*0.4, wacc_base+0.02, 0.02)
        # Base
        v_bas, flows_bas, pv_f, pv_t = dcf_engine(fcf_in, g1, g2, wacc_base, gt)
        # Alcista
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.03, g2+0.02, wacc_base-0.015, 0.03)

        c_esc1.markdown(f'<div class="scenario-card"><span class="label-bajista">Bajista</span><div class="metric-costco">${v_baj:.0f}</div><div style="color:red">{(v_baj/p_actual-1)*100:.1f}% vs actual</div><small>WACC {(wacc_base+0.02)*100:.1f}%</small></div>', unsafe_allow_html=True)
        c_esc2.markdown(f'<div class="scenario-card"><span class="label-base">Base</span><div class="metric-costco">${v_bas:.0f}</div><div style="color:orange">{(v_bas/p_actual-1)*100:.1f}% vs actual</div><small>WACC {wacc_base*100:.1f}%</small></div>', unsafe_allow_html=True)
        c_esc3.markdown(f'<div class="scenario-card"><span class="label-alcista">Alcista</span><div class="metric-costco">${v_alc:.0f}</div><div style="color:green">{(v_alc/p_actual-1)*100:.1f}% vs actual</div><small>WACC {(wacc_base-0.015)*100:.1f}%</small></div>', unsafe_allow_html=True)

        st.markdown("---")
        # Donut Chart
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_f, pv_t], hole=.6, marker_colors=['#3498db', '#f39c12'])])
        fig_donut.update_layout(title="Composición del Valor Intrínseco", height=400, template="plotly_white")
        st.plotly_chart(fig_donut, use_container_width=True)

    # --- TAB 1: VALORACIÓN PRO ---
    with tabs[1]:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Sensibilidad: WACC vs Crecimiento Terminal")
            w_range = np.linspace(wacc_base-0.02, wacc_base+0.02, 5)
            g_range = np.linspace(0.015, 0.035, 5)
            matrix = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in g_range] for w in w_range]
            df_sens = pd.DataFrame(matrix, index=[f"W:{x*100:.1f}%" for x in w_range], columns=[f"g:{x*100:.1f}%" for x in g_range])
            st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_white"), use_container_width=True)
        with c2:
            st.subheader("Flujos Proyectados")
            st.bar_chart(flows_bas)
            st.info("💡 El gráfico muestra el FCF anual descontado. Nota el salto en el año 6 debido a la transición de etapas.")

    # --- TAB 2: BENCHMARKING ---
    with tabs[2]:
        idx = st.selectbox("Benchmark de Mercado:", ["S&P 500", "NASDAQ 100", "Dow Jones"])
        pe_b = {"S&P 500": 22.5, "NASDAQ 100": 29.2, "Dow Jones": 19.5}[idx]
        df_p = pd.DataFrame({'Ticker': ['COST', 'WMT', 'TGT', 'BJ', idx], 'PE': [52.4, 31.2, 17.5, 21.1, pe_b], 'Growth': [9.5, 6.2, 4.5, 8.2, 7.5]})
        
        col_b1, col_b2 = st.columns(2)
        col_b1.plotly_chart(px.bar(df_p, x='Ticker', y='PE', color='Ticker', title="P/E Comparativo", template="plotly_white"), use_container_width=True)
        col_b2.plotly_chart(px.scatter(df_p, x='Growth', y='PE', text='Ticker', size='PE', color='Ticker', title="Crecimiento vs Valuación", template="plotly_white"), use_container_width=True)

    # --- TAB 3: MONTE CARLO ---
    with tabs[3]:
        st.subheader("Simulación Monte Carlo (1,000 Escenarios)")
        vol_mc = st.slider("Volatilidad de Supuestos", 0.01, 0.05, 0.02)
        sims = [dcf_engine(fcf_in, np.random.normal(g1, vol_mc), g2, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_actual).mean() * 100
        fig_mc = px.histogram(sims, nbins=40, title=f"Probabilidad de ser rentables: {prob_success:.1f}%", template="plotly_white", color_discrete_sequence=['#27ae60'])
        fig_mc.add_vline(x=p_actual, line_color="red", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)

    # --- TAB 4: STRESS TEST ---
    with tabs[4]:
        adj_g = g1 + (disposable_inc/200) - (unemployment/500)
        adj_w = wacc_base + (cpi/500) + (wage_press/1000)
        v_str, _ , _, _ = dcf_engine(fcf_in, adj_g, g2, adj_w, 0.025)
        st.metric("Valor Post-Estrés", f"${v_str:.2f}", f"{((v_str/v_bas)-1)*100:.1f}% vs Caso Base")
        st.write(f"**Análisis:** Bajo este escenario, el WACC sube a **{adj_w*100:.2f}%** y el crecimiento baja a **{adj_g*100:.2f}%**.")

    # --- TAB 5: OPCIONES ---
    with tabs[5]:
        o_t = st.radio("Contrato", ["Call", "Put"])
        k = st.number_input("Strike", value=float(round(p_actual*1.05, 0)))
        iv = st.slider("IV %", 5, 100, 25) / 100
        res = calculate_full_greeks(p_actual, k, 30/365, 0.045, iv, o_t.lower())
        
        c_o1, c_o2 = st.columns(2)
        with c_o1:
            st.metric("Precio Prima", f"${res['price']:.2f}")
            st.write(f"**Delta:** {res['delta']:.3f} | **Gamma:** {res['gamma']:.4f}")
            st.write(f"**Vega:** {res['vega']:.3f} | **Theta (Día):** ${res['theta']:.2f} | **Rho:** {res['rho']:.3f}")
        with c_o2:
            x_r = np.linspace(p_actual*0.8, p_actual*1.2, 50)
            deltas = [calculate_full_greeks(x, k, 30/365, 0.045, iv, o_t.lower())['delta'] for x in x_r]
            st.plotly_chart(px.line(x=x_r, y=deltas, title="Curva de Sensibilidad Delta", template="plotly_white"), use_container_width=True)

    # --- TAB 6: MASTERCLASS ---
    with tabs[6]:
        st.header("📚 Guía Metodológica Institucional")
        with st.expander("💰 1. El WACC y el Coste de Oportunidad", expanded=True):
            st.write("El WACC es la rentabilidad mínima exigida. Usamos la Beta (0.79) para calcular el coste del capital propio (CAPM).")
            st.latex(r"K_e = R_f + \beta (R_m - R_f)")
        with st.expander("🎲 2. Simulación de Monte Carlo"):
            st.write("No predecimos el futuro; medimos la probabilidad. Al variar los supuestos 1,000 veces, obtenemos una campana de Gauss que nos indica el margen de seguridad real.")
        with st.expander("🌪️ 3. Stress Test y Macro"):
            st.write("Evaluamos la resiliencia. Costco es 'defensiva' porque su Beta es baja y sus flujos son estables incluso con desempleo alto o inflación.")

if __name__ == "__main__":
    main()
