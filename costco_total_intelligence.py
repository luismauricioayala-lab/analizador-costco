import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

# Estilo para asegurar legibilidad en Modo Claro y Oscuro
st.markdown("""
    <style>
    .metric-container { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 5px; padding: 10px 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES MATEMÁTICOS ---
def run_dcf(fcf_base, g1, g2, wacc, gt, shares=0.44365, cash=22.0):
    flows = []
    curr = fcf_base
    for i in range(1, 11):
        curr *= (1 + g1) if i <= 5 else (1 + g2)
        flows.append(curr)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(flows, 1)])
    tv = (flows[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, flows, pv_f, pv_t

def get_options_data(S, K, T, r, sigma, type='call'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
    return price, delta

# --- 3. INTERFAZ PRINCIPAL ---
def main():
    st.title("Costco Wholesale (COST) — Institutional Intelligence Hub")
    st.caption("v6.5 Build 2026 • Análisis Fundamental, Probabilístico y Macroeconómico")

    # --- SIDEBAR (TODOS LOS INPUTS) ---
    st.sidebar.header("🎯 Supuestos del Analista")
    p_mercado = st.sidebar.number_input("Precio Actual COST ($)", value=950.0)
    
    with st.sidebar.expander("📈 Parámetros DCF", expanded=True):
        fcf_in = st.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
        wacc_in = st.slider("WACC (%)", 5.0, 15.0, 8.5) / 100
        g1 = st.slider("Crecimiento Años 1-5 (%)", 1, 20, 12) / 100
        g2 = st.slider("Crecimiento Años 6-10 (%)", 1, 15, 8) / 100
        gt = 0.025 # Crecimiento Terminal

    with st.sidebar.expander("🌪️ Variables de Stress Test"):
        pib = st.slider("Crecimiento PIB (%)", -5.0, 5.0, 2.0)
        desempleo = st.slider("Tasa Desempleo (%)", 3.0, 15.0, 4.5)
        income = st.slider("Ingreso Disponible (%)", -10, 10, 0)
        inflacion = st.slider("Inflación (CPI) %", 0, 10, 3)

    # --- HEADER METRICS ---
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Market Cap", "$450.2B", "COST-NASDAQ")
    h2.metric("P/E TTM", "51.8x", "Premium")
    h3.metric("FCF Yield", "2.1%", "Sano")
    h4.metric("Beta", "0.79", "Defensivo")

    st.markdown("---")

    # --- TABS ---
    t1, t2, t3, t4, t5 = st.tabs(["💎 Valoración Pro", "📊 Mercado & Peers", "🎲 Monte Carlo", "🌪️ Stress Lab", "📉 Opciones Lab"])

    # --- TAB 1: VALORACIÓN ---
    with t1:
        # Ajuste de WACC por Inflación
        adj_wacc = wacc_in + (inflacion/500)
        fv, flows, pv_f, pv_t = run_dcf(fcf_in, g1, g2, adj_wacc, gt)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Proyección FCF 10 Años")
            fig_flows = go.Figure(data=[go.Bar(x=[f"A{i}" for i in range(1,11)], y=flows, marker_color='#2ecc71')])
            fig_flows.update_layout(template="plotly_white", height=300)
            st.plotly_chart(fig_flows, use_container_width=True)
            
            st.subheader("Sensibilidad: WACC vs Crecimiento Terminal")
            w_s = np.linspace(adj_wacc-0.02, adj_wacc+0.02, 5)
            g_s = np.linspace(0.015, 0.035, 5)
            matrix = [[run_dcf(fcf_in, g1, g2, w, g)[0] for g in g_s] for w in w_s]
            df_sens = pd.DataFrame(matrix, index=[f"{x*100:.1f}%" for x in w_s], columns=[f"{x*100:.1f}%" for x in g_s])
            st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_white"), use_container_width=True)

        with c2:
            st.subheader("Veredicto Intrínseco")
            upside = (fv/p_mercado - 1)*100
            st.metric("Fair Value", f"${fv:.2f}", f"{upside:.1f}% Upside")
            st.write(f"**PV Flujos:** ${pv_f:.1f}B")
            st.write(f"**PV Terminal:** ${pv_t:.1f}B")
            st.write(f"**WACC Ajustado:** {adj_wacc*100:.2f}%")

    # --- TAB 2: BENCHMARK & PEERS ---
    with t2:
        st.subheader("Análisis de Benchmarking de Mercado")
        benchmark_name = st.selectbox("Benchmark", ["S&P 500", "NASDAQ 100", "Dow Jones"])
        bench_data = {"S&P 500": 22.5, "NASDAQ 100": 29.2, "Dow Jones": 19.5}
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            comp_df = pd.DataFrame({
                "Ticker": ["COST", "WMT", "TGT", benchmark_name],
                "P/E Ratio": [51.8, 31.2, 17.5, bench_data[benchmark_name]]
            })
            st.plotly_chart(px.bar(comp_df, x="Ticker", y="P/E Ratio", color="Ticker", template="plotly_white"), use_container_width=True)
        with col_b2:
            st.write(f"**Análisis:** Costco cotiza con una prima del {((51.8/bench_data[benchmark_name])-1)*100:.1f}% respecto al {benchmark_name}.")

    # --- TAB 3: MONTE CARLO ---
    with t3:
        st.subheader("Simulación de Probabilidad Monte Carlo (1,000 Escenarios)")
        vol_mc = st.slider("Volatilidad de Supuestos", 0.01, 0.05, 0.02)
        sims = [run_dcf(fcf_in, np.random.normal(g1, vol_mc), g2, np.random.normal(adj_wacc, 0.005), gt)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_mercado).mean() * 100
        
        fig_mc = px.histogram(sims, nbins=40, title=f"Probabilidad de Éxito: {prob_success:.1f}%", template="plotly_white", color_discrete_sequence=['#3498db'])
        fig_mc.add_vline(x=p_mercado, line_color="red", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)

    # --- TAB 4: STRESS TEST GRANULAR ---
    with t4:
        st.subheader("Laboratorio de Estrés Macroeconómico")
        # Ajuste Granular
        adj_g_stress = g1 + (income/200) - (desempleo/500) + (pib/150)
        fv_stress, _ , _, _ = run_dcf(fcf_in, adj_g_stress, g2, adj_wacc, gt)
        
        s_col1, s_col2 = st.columns(2)
        s_col1.metric("Valor Post-Estrés", f"${fv_stress:.2f}", f"{((fv_stress/fv)-1)*100:.1f}% vs Caso Base")
        s_col2.write(f"**Impacto en Crecimiento:** Tu escenario macro ajusta el crecimiento de Costco al **{adj_g_stress*100:.2f}%**.")
        
        if fv_stress < p_mercado:
            st.error("🚨 La acción no resiste este escenario macro: el precio de mercado supera el valor intrínseco estresado.")
        else:
            st.success("✅ Costco demuestra resiliencia bajo este escenario.")

    # --- TAB 5: OPCIONES ---
    with t5:
        st.subheader("Análisis Profesional de Opciones")
        o_c1, o_c2 = st.columns(2)
        with o_c1:
            strike = st.number_input("Precio Strike ($)", value=float(round(p_mercado*1.05, 0)))
            iv = st.slider("Volatilidad Implícita (IV %)", 10, 100, 25) / 100
            o_p, o_d = get_options_data(p_mercado, strike, 30/365, 0.045, iv)
            st.metric("Prima del Call (30d)", f"${o_p:.2f}")
            st.metric("Delta", f"{o_d:.3f}")
        with o_c2:
            x_p = np.linspace(p_mercado*0.8, p_mercado*1.2, 100)
            y_p = np.maximum(x_p - strike, 0) - o_p
            fig_opt = go.Figure(go.Scatter(x=x_p, y=y_p, fill='tozeroy', name='P&L'))
            fig_opt.update_layout(title="Payoff al Vencimiento", template="plotly_white", xaxis_title="Precio COST", yaxis_title="Ganancia/Pérdida")
            st.plotly_chart(fig_opt, use_container_width=True)

if __name__ == "__main__":
    main()