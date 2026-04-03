import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

# CSS para un look profesional y limpio
st.markdown("""
    <style>
    .stMetric { border: 1px solid rgba(128, 128, 128, 0.2); padding: 15px; border-radius: 10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { padding: 10px 20px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE CÁLCULO (ENGINE) ---
def calculate_dcf(fcf, g1, g2, wacc, gt, shares=0.44365, cash=22.0):
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

# --- 3. DATOS DE MERCADO Y PEERS ---
PEERS_DATA = pd.DataFrame({
    'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500', 'NASDAQ'],
    'Nombre': ['Costco', 'Walmart', 'Target', "BJ's", 'Amazon', 'Mercado', 'Tecnología'],
    'PE': [52.4, 31.2, 17.5, 21.1, 45.0, 22.5, 29.2],
    'Rev_Growth': [9.5, 6.2, 4.5, 8.2, 12.5, 7.0, 11.0],
    'EV_EBITDA': [32.4, 15.2, 11.1, 12.8, 22.0, 13.0, 16.0],
    'Margin': [2.6, 2.4, 3.8, 1.9, 5.1, 11.0, 15.0]
})

# --- 4. INTERFAZ PRINCIPAL ---
def main():
    st.title("🏛️ COST Institutional Intelligence Hub")
    st.caption("Terminal v7.0 • Análisis de Escenarios, Simulación Estocástica y Benchmarking Relativo")

    # --- SIDEBAR (INPUTS BASE) ---
    st.sidebar.header("🎯 Supuestos del Analista")
    p_actual = st.sidebar.number_input("Precio Actual COST ($)", value=950.0)
    fcf_base = st.sidebar.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
    wacc_base = st.sidebar.slider("WACC Base (%)", 5.0, 15.0, 8.5) / 100
    g1_base = st.sidebar.slider("Crecimiento Años 1-5 (%)", 1, 20, 12) / 100
    g2_base = st.sidebar.slider("Crecimiento Años 6-10 (%)", 1, 15, 8) / 100

    # --- HEADER METRICS ---
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("P/E TTM", "52.4x", "Premium vs Sector")
    h2.metric("Market Cap", "$450.2B", "NASDAQ: COST")
    h3.metric("Beta", "0.79", "Baja Volatilidad")
    h4.metric("Membership Rate", "92.4%", "Alta Fidelidad")

    st.markdown("---")

    # --- TABS ---
    t_dcf, t_bench, t_mc, t_stress, t_options = st.tabs([
        "💎 Valoración DCF", "📊 Benchmark & Peers", "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Options Strategy"
    ])

    # --- TAB 1: VALORACIÓN ---
    with t_dcf:
        fv, flows = calculate_dcf(fcf_base, g1_base, g2_base, wacc_base, 0.025)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Proyección FCF a 10 años")
            fig_flows = go.Figure(data=[go.Bar(x=[f"A{i}" for i in range(1,11)], y=flows, marker_color='#2ecc71')])
            fig_flows.update_layout(template="plotly_white", height=350)
            st.plotly_chart(fig_flows, use_container_width=True)
        with c2:
            st.subheader("Veredicto de Valor")
            st.metric("Fair Value Estimado", f"${fv:.2f}", f"{(fv/p_actual-1)*100:.1f}% Upside")
            st.info("💡 Este valor asume condiciones de mercado estables y crecimiento constante.")

    # --- TAB 2: BENCHMARK & PEERS (BARRAS Y SCATTER) ---
    with t_bench:
        st.subheader("Análisis Comparativo de Mercado")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write("**P/E Ratio: COST vs Pares e Índices**")
            fig_bar = px.bar(PEERS_DATA, x='Ticker', y='PE', color='Ticker', template="plotly_white")
            st.plotly_chart(fig_bar, use_container_width=True)
            

        with col_b2:
            st.write("**Valuación vs Crecimiento (Scatter Plot)**")
            fig_scatter = px.scatter(PEERS_DATA, x='Rev_Growth', y='PE', text='Ticker', size='Margin', color='Ticker', 
                                     template="plotly_white", labels={'Rev_Growth': 'Crecimiento Ventas (%)', 'PE': 'P/E Ratio'})
            st.plotly_chart(fig_scatter, use_container_width=True)
            

    # --- TAB 3: MONTE CARLO (INTUITIVO) ---
    with t_mc:
        st.subheader("Análisis Probabilístico de Monte Carlo")
        vol_param = st.slider("Incertidumbre de Supuestos (Volatilidad %)", 1, 10, 3) / 100
        
        # Simulación
        np.random.seed(42)
        sims = [calculate_dcf(fcf_base, np.random.normal(g1_base, vol_param), g2_base, 
                              np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_actual).mean() * 100
        
        c_mc1, c_mc2 = st.columns([2, 1])
        with c_mc1:
            fig_hist = px.histogram(sims, nbins=40, title="Distribución de Resultados Posibles", 
                                    template="plotly_white", color_discrete_sequence=['#3498db'])
            fig_hist.add_vline(x=p_actual, line_color="red", line_dash="dash", annotation_text="Precio de Mercado")
            st.plotly_chart(fig_hist, use_container_width=True)
            
        with c_mc2:
            st.write("### ¿Qué significa esto?")
            st.write(f"Hemos simulado **1,000 futuros posibles** variando el crecimiento y el riesgo.")
            st.metric("Probabilidad de Éxito", f"{prob_success:.1f}%", help="Porcentaje de escenarios donde COST vale más de lo que cuesta hoy.")
            if prob_success > 50: st.success("La mayoría de los escenarios son favorables.")
            else: st.error("El riesgo de sobrevaloración es alto en este modelo.")

    # --- TAB 4: STRESS TEST LAB (INTERACTIVO Y GRANULAR) ---
    with t_stress:
        st.header("🌪️ Laboratorio de Estrés Macroeconómico")
        st.write("Ajusta variables granulares para ver cómo impactan el Valor Intrínseco en tiempo real.")
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.subheader("Consumo")
            disposable_income = st.slider("Ingreso Disponible (%)", -10, 5, 0)
            unemployment = st.slider("Tasa Desempleo (%)", 3, 12, 4)
        with col_s2:
            st.subheader("Costos e Inflación")
            cpi = st.slider("Inflación CPI (%)", 0, 10, 3)
            wage_hike = st.slider("Alza Salarial (%)", 0, 8, 4)
        with col_s3:
            st.subheader("Eventos Swans")
            supply_chain = st.checkbox("Crisis de Suministros")
            cyber_event = st.checkbox("Ciberataque")

        # LÓGICA DE IMPACTO
        # El ingreso disponible y el desempleo afectan g1
        adj_g1 = g1_base + (disposable_income / 150) - (unemployment / 400)
        # La inflación y alzas salariales afectan el WACC
        adj_wacc = wacc_base + (cpi / 500) + (wage_hike / 1000)
        # Cisnes Negros
        if supply_chain: adj_g1 -= 0.04; adj_wacc += 0.01
        if cyber_event: adj_g1 -= 0.02; adj_wacc += 0.005
        
        v_stress, _ = calculate_dcf(fcf_base, adj_g1, g2_base, adj_wacc, 0.025)
        
        st.markdown("---")
        st.subheader("Resultado del Escenario de Estrés")
        s_m1, s_m2, s_m3 = st.columns(3)
        s_m1.metric("Valor Post-Estrés", f"${v_stress:.2f}", f"{((v_stress/fv)-1)*100:.1f}% vs Base")
        s_m2.metric("WACC Ajustado", f"{adj_wacc*100:.2f}%")
        s_m3.metric("Crecimiento Ajustado", f"{adj_g1*100:.1f}%")
        
        

# --- TAB 5: OPCIONES PROFUNDO ---
    with tabs[4]:
        st.header("🔬 Options Analysis & Risk Greeks")
        st.info("💡 Este laboratorio calcula la sensibilidad de tu contrato ante cambios en precio, tiempo y volatilidad.")
        
        c_op1, c_op2 = st.columns([1, 2])
        
        with c_op1:
            st.subheader("Configuración")
            op_type = st.selectbox("Tipo de Contrato", ["Call", "Put"])
            k_strike = st.number_input("Precio Strike ($)", value=float(round(p_mercado * 1.05, 0)))
            t_days = st.slider("Días al Vencimiento", 1, 365, 30)
            iv = st.slider("Volatilidad Implícita (IV %)", 5, 100, 25) / 100
            r_rate = 0.045 # Treasury 10Y aprox.

            res = calculate_options_master(p_mercado, k_strike, t_days/365, r_rate, iv, op_type.lower())
            
            st.markdown("---")
            st.metric("Precio Teórico", f"${res['price']:.2f}")
            
            st.subheader("Griegas (Greeks)")
            g_col1, g_col2 = st.columns(2)
            g_col1.write(f"**Delta:** {res['delta']:.3f}")
            g_col1.write(f"**Gamma:** {res['gamma']:.4f}")
            g_col1.write(f"**Vega:** {res['vega']:.3f}")
            g_col2.write(f"**Theta (Día):** ${res['theta']:.2f}")
            g_col2.write(f"**Rho:** {res['rho']:.3f}")

        with c_op2:
            st.subheader("Simulación de Sensibilidad")
            # Gráfico de Delta vs Precio de la Acción
            prices_range = np.linspace(p_mercado * 0.8, p_mercado * 1.2, 50)
            deltas = [calculate_options_master(p, k_strike, t_days/365, r_rate, iv, op_type.lower())['delta'] for p in prices_range]
            
            fig_delta = go.Figure()
            fig_delta.add_trace(go.Scatter(x=prices_range, y=deltas, name='Delta Sensitivity', line=dict(color='#3498db', width=3)))
            fig_delta.update_layout(title="Sensibilidad de la Delta vs Precio Spot", template="plotly_white", xaxis_title="Precio COST", yaxis_title="Delta")
            st.plotly_chart(fig_delta, use_container_width=True)

            # Análisis de Profundidad
            st.subheader("Análisis del Analista")
            if abs(res['delta']) > 0.7:
                st.warning("⚠️ **Deep in the Money:** La opción se comporta casi como la acción. Riesgo direccional máximo.")
            elif abs(res['delta']) < 0.3:
                st.info("ℹ️ **Out of the Money:** Alto apalancamiento, pero alta probabilidad de que expire sin valor.")
            
            st.write(f"**Impacto de Volatilidad:** Por cada 1% que suba la IV, tu contrato ganará/perderá aproximadamente **${abs(res['vega']):.2f}**.")
            st.write(f"**Decaimiento Temporal:** Estás perdiendo **${abs(res['theta']):.2f}** diarios solo por el paso del tiempo.")

if __name__ == "__main__":
    main()