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
    [data-testid="stMetricValue"] { font-size: 26px !important; }
    .educational-box { background-color: rgba(35, 134, 54, 0.1); padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES MATEMÁTICOS ---
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
    st.title("🏛️ COST Institutional Intelligence Hub")
    st.caption("Terminal v8.0 • Análisis 360°: Fundamental, Macro, Probabilístico y Derivados")

    # --- SIDEBAR ---
    st.sidebar.header("🎯 Supuestos del Analista")
    p_actual = st.sidebar.number_input("Precio Actual COST ($)", value=950.0)
    fcf_base = st.sidebar.slider("FCF Base ($B)", 5.0, 15.0, 9.5)
    wacc_base = st.sidebar.slider("WACC Base (%)", 5.0, 15.0, 8.5) / 100
    g1_base = st.sidebar.slider("Crecimiento Años 1-5 (%)", 1, 25, 12) / 100
    g2_base = st.sidebar.slider("Crecimiento Años 6-10 (%)", 1, 20, 8) / 100

    # --- HEADER METRICS ---
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("P/E TTM", "52.4x", "Premium vs Sector")
    h2.metric("Market Cap", "$450.2B", "NASDAQ: COST")
    h3.metric("Beta", "0.79", "Defensivo")
    h4.metric("Membership Rate", "92.4%", "Retention Leader")

    st.markdown("---")
    tabs = st.tabs(["💎 Valoración DCF", "📊 Benchmark & Peers", "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Opciones & Griegas", "📚 Metodología & Beta"])

    # --- TAB 1: VALORACIÓN ---
    with tabs[0]:
        fv, flows = calculate_dcf(fcf_base, g1_base, g2_base, wacc_base, 0.025)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Sensibilidad: WACC vs Crecimiento Terminal")
            w_range = np.linspace(wacc_base-0.02, wacc_base+0.02, 5)
            g_range = np.linspace(0.015, 0.035, 5)
            matrix = [[calculate_dcf(fcf_base, g1_base, g2_base, w, g)[0] for g in g_range] for w in w_range]
            df_sens = pd.DataFrame(matrix, index=[f"{x*100:.1f}%" for x in w_range], columns=[f"{x*100:.1f}%" for x in g_range])
            st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_white"), use_container_width=True)
        with c2:
            st.metric("Fair Value Estimado", f"${fv:.2f}", f"{(fv/p_actual-1)*100:.1f}% Upside")
            st.write("**Proyección de Flujos (10 años):**")
            st.bar_chart(flows)
            

    # --- TAB 2: BENCHMARK & PEERS ---
    with tabs[1]:
        st.subheader("Análisis de Mercado y Competidores")
        idx_bench = st.selectbox("Seleccionar Benchmark para comparar:", ["S&P 500", "NASDAQ", "Walmart", "Target"])
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.plotly_chart(px.bar(PEERS_DATA, x='Ticker', y='PE', color='Ticker', title="P/E Ratio Comparativo", template="plotly_white"), use_container_width=True)
        with col_b2:
            st.plotly_chart(px.scatter(PEERS_DATA, x='Rev_Growth', y='PE', text='Ticker', size='Margin', color='Ticker', title="Crecimiento vs Valuación", template="plotly_white"), use_container_width=True)
        

    # --- TAB 3: MONTE CARLO ---
    with tabs[2]:
        st.subheader("Simulación de Probabilidad Monte Carlo")
        vol_mc = st.slider("Volatilidad de Supuestos", 0.01, 0.05, 0.02)
        sims = [calculate_dcf(fcf_base, np.random.normal(g1_base, vol_mc), g2_base, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_actual).mean() * 100
        
        fig_mc = px.histogram(sims, nbins=40, title=f"Probabilidad de Éxito: {prob_success:.1f}%", template="plotly_white", color_discrete_sequence=['#27ae60'])
        fig_mc.add_vline(x=p_actual, line_color="red", line_dash="dash", annotation_text="Precio Actual")
        st.plotly_chart(fig_mc, use_container_width=True)
        

    # --- TAB 4: STRESS TEST ---
    with tabs[3]:
        st.header("🌪️ Laboratorio de Estrés Macroeconómico")
        s1, s2, s3 = st.columns(3)
        with s1:
            inc = s1.slider("Ingreso Disponible %", -10, 5, 0)
            unemp = s1.slider("Desempleo %", 3, 15, 4)
        with s2:
            cpi = s2.slider("Inflación (CPI) %", 0, 10, 3)
            wage_press = s2.slider("Alza Salarial %", 0, 8, 4)
        with s3:
            swan_event = st.checkbox("Crisis Geopolítica / Logística")

        adj_g = g1_base + (inc/200) - (unemp/500) - (0.04 if swan_event else 0)
        adj_wacc = wacc_base + (cpi/500) + (wage_press/1000)
        v_stress, _ = calculate_dcf(fcf_base, adj_g, g2_base, adj_wacc, 0.025)
        
        st.metric("Valor Post-Estrés", f"${v_stress:.2f}", f"{((v_stress/fv)-1)*100:.1f}% vs Caso Base")
        

    # --- TAB 5: OPCIONES & GRIEGAS ---
    with tabs[4]:
        st.header("🔬 Deep Options Analysis")
        o_c1, o_c2 = st.columns([1, 2])
        with o_c1:
            o_type = st.radio("Tipo", ["Call", "Put"])
            strike = st.number_input("Strike Price ($)", value=float(round(p_actual * 1.05, 0)))
            days = st.slider("Días al Vencimiento", 1, 365, 30)
            sigma = st.slider("Volatilidad Implícita (IV %)", 5, 100, 25) / 100
            
            res = calculate_full_greeks(p_actual, strike, days/365, 0.045, sigma, o_type.lower())
            
            st.metric("Prima del Contrato", f"${res['price']:.2f}")
            st.write(f"**Delta:** {res['delta']:.3f} | **Gamma:** {res['gamma']:.4f}")
            st.write(f"**Vega:** {res['vega']:.3f} | **Theta (Día):** ${res['theta']:.2f}")
            st.write(f"**Rho:** {res['rho']:.3f}")
        with o_c2:
            st.subheader("Curva de Sensibilidad Delta")
            x_range = np.linspace(p_actual*0.8, p_actual*1.2, 50)
            deltas = [calculate_full_greeks(x, strike, days/365, 0.045, sigma, o_type.lower())['delta'] for x in x_range]
            st.plotly_chart(px.line(x=x_range, y=deltas, labels={'x': 'Precio COST', 'y': 'Delta'}, template="plotly_white"), use_container_width=True)
            

    # --- TAB 6: METODOLOGÍA & BETA ---
    with tabs[5]:
        st.header("📚 Metodología: La Beta y su Resiliencia")
        st.markdown("""
        <div class='educational-box'>
        Costco presenta una <b>Beta (β) de 0.79</b>. Esto la clasifica como una acción <b>defensiva</b> por excelencia.
        </div>
        """, unsafe_allow_html=True)
        
        e1, e2 = st.columns(2)
        with e1:
            st.subheader("¿Por qué es defensiva?")
            st.write("""
            - **Baja Volatilidad:** Al ser un 21% menos volátil que el S&P 500, protege el capital en mercados bajistas.
            - **Consumer Staples:** La gente no deja de comprar comida o suministros básicos en Costco, incluso si hay crisis.
            - **Membresías:** Sus ingresos no dependen solo de las ventas, sino de las cuotas de socios, lo que da estabilidad extrema.
            """)
        with e2:
            st.subheader("Impacto en la Valoración (CAPM)")
            st.latex(r"K_e = R_f + \beta (R_m - R_f)")
            st.info("Una Beta baja reduce el coste del capital (WACC), lo que eleva matemáticamente el Valor Intrínseco de la empresa.")
            

if __name__ == "__main__":
    main()
