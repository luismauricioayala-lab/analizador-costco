import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

# CSS para estilo Bloomberg/Terminal
st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.1); }
    .scenario-card { background-color: white; border-radius: 15px; padding: 20px; border: 1px solid #e0e0e0; text-align: center; color: #1c1c1c; }
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
    'PE': [51.8, 31.2, 17.5, 21.1, 45.0, 22.5, 29.2],
    'Rev_Growth': [9.5, 6.2, 4.5, 8.2, 12.5, 7.0, 11.0],
    'Margin': [2.6, 2.4, 3.8, 1.9, 5.1, 11.0, 15.0]
})

# --- 4. INTERFAZ PRINCIPAL ---
def main():
    st.title("🏛️ Costco Wholesale (COST) — Master Intelligence Terminal")
    
    # --- SIDEBAR: SUPUESTOS BASE ---
    st.sidebar.header("🎯 Supuestos Base del Analista")
    p_actual = st.sidebar.number_input("Precio Mercado ($)", value=950.0)
    fcf_in = st.sidebar.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
    g1_base = st.sidebar.slider("Crecimiento Años 1-5 (%)", 1, 25, 12) / 100
    g2_base = st.sidebar.slider("Crecimiento Años 6-10 (%)", 1, 20, 8) / 100
    wacc_base = st.sidebar.slider("WACC Base (%)", 5.0, 15.0, 8.5) / 100
    gt = 0.025 

# --- BLOQUE DE DESCARGA DE GUÍA ---
    import os
    if os.path.exists("Guia_Metodologica_COST.pdf"):
        with open("Guia_Metodologica_COST.pdf", "rb") as file:
            st.sidebar.download_button(
                label="📄 Descargar Guía Metodológica",
                data=file,
                file_name="Guia_Metodologica_COST.pdf",
                mime="application/pdf"
            )
    else:
        st.sidebar.info("📌 Sube el archivo 'Guia_Metodologica_COST.pdf' a tu repositorio para activar la descarga.")

    # CÁLCULO CASO BASE PARA REFERENCIA
    v_base_ref, flows_base, pv_f_base, pv_t_base = dcf_engine(fcf_in, g1_base, g2_base, wacc_base, gt)

    # HEADER METRICS
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("P/E TTM", "51.8x", "Premium")
    h2.metric("Market Cap", "$450.2B", "COST-NASDAQ")
    h3.metric("Beta", "0.79", "Defensivo")
    h4.metric("Retention", "92.4%", "Gold Standard")

    st.markdown("---")
    tabs = st.tabs(["📋 Resumen Ejecutivo", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Opciones Lab", "📚 Metodología Masterclass"])

    # --- TAB 0: ESCENARIOS (Visual) ---
    with tabs[0]:
        c_esc1, c_esc2, c_esc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1_base*0.5, g2_base*0.4, wacc_base+0.02, 0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1_base+0.03, g2_base+0.02, wacc_base-0.015, 0.03)

        c_esc1.markdown(f'<div class="scenario-card"><span class="label-bajista">Bajista</span><div class="metric-costco">${v_baj:.0f}</div><div style="color:red">{(v_baj/p_actual-1)*100:.1f}% vs actual</div><small>WACC {(wacc_base+0.02)*100:.1f}%</small></div>', unsafe_allow_html=True)
        c_esc2.markdown(f'<div class="scenario-card"><span class="label-base">Base</span><div class="metric-costco">${v_base_ref:.0f}</div><div style="color:orange">{(v_base_ref/p_actual-1)*100:.1f}% vs actual</div><small>WACC {wacc_base*100:.1f}%</small></div>', unsafe_allow_html=True)
        c_esc3.markdown(f'<div class="scenario-card"><span class="label-alcista">Alcista</span><div class="metric-costco">${v_alc:.0f}</div><div style="color:green">{(v_alc/p_actual-1)*100:.1f}% vs actual</div><small>WACC {(wacc_base-0.015)*100:.1f}%</small></div>', unsafe_allow_html=True)
        
        st.markdown("---")
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_f_base, pv_t_base], hole=.6, marker_colors=['#3498db', '#f39c12'])])
        fig_donut.update_layout(title="Composición del Valor Intrínseco (Caso Base)", height=400, template="plotly_white")
        st.plotly_chart(fig_donut, use_container_width=True)

    # --- TAB 1: VALORACIÓN ---
    with tabs[1]:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Matriz de Sensibilidad: WACC vs G Terminal")
            w_range = np.linspace(wacc_base-0.02, wacc_base+0.02, 5)
            g_range = np.linspace(0.015, 0.035, 5)
            matrix = [[dcf_engine(fcf_in, g1_base, g2_base, w, g)[0] for g in g_range] for w in w_range]
            df_sens = pd.DataFrame(matrix, index=[f"W:{x*100:.1f}%" for x in w_range], columns=[f"g:{x*100:.1f}%" for x in g_range])
            st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_white"), use_container_width=True)
        with c2:
            st.subheader("FCF Proyectado")
            st.bar_chart(flows_base)

    # --- TAB 2: BENCHMARKING (BARRAS Y SCATTER FIJOS) ---
    with tabs[2]:
        st.subheader("Análisis de Mercado: COST vs Pares e Índices")
        st.caption("Comparación directa contra Walmart, Target, BJ's, Amazon y Benchmarks principales.")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            fig_bar = px.bar(PEERS_DATA, x='Ticker', y='PE', color='Ticker', title="P/E Ratio Comparativo", template="plotly_white", color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_bar, use_container_width=True)
        with col_b2:
            fig_scatter = px.scatter(PEERS_DATA, x='Rev_Growth', y='PE', text='Ticker', size='PE', color='Ticker', title="Crecimiento vs Valuación", template="plotly_white")
            st.plotly_chart(fig_scatter, use_container_width=True)

    # --- TAB 3: MONTE CARLO ---
    with tabs[3]:
        st.subheader("Simulación Monte Carlo (1,000 Escenarios)")
        vol_mc = st.slider("Incertidumbre de Supuestos", 0.01, 0.05, 0.02)
        sims = [dcf_engine(fcf_in, np.random.normal(g1_base, vol_mc), g2_base, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_actual).mean() * 100
        fig_mc = px.histogram(sims, nbins=40, title=f"Probabilidad de Éxito: {prob_success:.1f}%", template="plotly_white", color_discrete_sequence=['#27ae60'])
        fig_mc.add_vline(x=p_actual, line_color="red", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)

    # --- TAB 4: STRESS TEST LAB (INTERACTIVO COMO EN LA IMAGEN) ---
    with tabs[4]:
        st.header("🌪️ Laboratorio de Estrés Macroeconómico")
        st.write("Ajusta las variables locales para ver el impacto inmediato en el valor de Costco.")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            s_income = st.slider("Ingreso Disponible %", -10, 5, 0)
            s_unemp = st.slider("Desempleo %", 3, 15, 4)
        with col_s2:
            s_cpi = st.slider("Inflación (CPI) %", 0, 10, 3)
            s_wage = st.slider("Alza Salarial %", 0, 8, 4)
        
        s_swan = st.checkbox("Crisis Geopolítica / Logística")

        # LÓGICA DE ESTRÉS
        adj_g = g1_base + (s_income/200) - (s_unemp/500) - (0.04 if s_swan else 0)
        adj_w = wacc_base + (s_cpi/500) + (s_wage/1000)
        v_stress, _, _, _ = dcf_engine(fcf_in, adj_g, g2_base, adj_w, 0.025)
        
        st.markdown("---")
        diff_base = (v_stress/v_base_ref - 1) * 100
        st.subheader("Valor Post-Estrés")
        st.markdown(f"# ${v_stress:.2f}")
        color_diff = "red" if diff_base < 0 else "green"
        st.markdown(f"<span style='color:{color_diff}'>{diff_base:.1f}% vs Caso Base</span>", unsafe_allow_html=True)

    # --- TAB 5: OPCIONES ---
    with tabs[5]:
        o_t = st.radio("Tipo", ["Call", "Put"])
        k = st.number_input("Strike Price", value=float(round(p_actual*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 5, 100, 25) / 100
        res = calculate_full_greeks(p_actual, k, 30/365, 0.045, iv, o_t.lower())
        
        co1, co2 = st.columns([1, 2])
        with co1:
            st.metric("Prima del Contrato", f"${res['price']:.2f}")
            st.write(f"**Delta:** {res['delta']:.3f} | **Gamma:** {res['gamma']:.4f}")
            st.write(f"**Vega:** {res['vega']:.3f} | **Theta (Día):** ${res['theta']:.2f}")
            st.write(f"**Rho:** {res['rho']:.3f}")
        with co2:
            x_r = np.linspace(p_actual*0.8, p_actual*1.2, 50)
            deltas = [calculate_full_greeks(x, k, 30/365, 0.045, iv, o_t.lower())['delta'] for x in x_r]
            st.plotly_chart(px.line(x=x_r, y=deltas, title="Sensibilidad Delta", template="plotly_white"), use_container_width=True)

    # --- TAB 6: MASTERCLASS ---
    with tabs[6]:
        st.header("📚 Guía Metodológica Institucional")
        with st.expander("📝 1. El WACC y el Coste del Capital"):
            st.write("Explicación de la Beta defensiva (0.79) y el modelo CAPM...")
            st.latex(r"K_e = R_f + \beta (R_m - R_f)")
        with st.expander("🎲 2. Simulación de Monte Carlo"):
            st.write("Análisis de probabilidad basado en la campana de Gauss...")
        with st.expander("🌪️ 3. Lógica de Estrés"):
            st.write("Cómo la inflación y el desempleo afectan el denominador del DCF...")

if __name__ == "__main__":
    main()
