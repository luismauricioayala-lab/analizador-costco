import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import norm

# --- CONFIGURACIÓN ESTÉTICA ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { background-color: #161b22; padding: 20px; border-radius: 12px; border: 1px solid #30363d; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #161b22; border-radius: 5px; padding: 10px 20px; color: #8b949e; }
    .stTabs [data-baseweb="tab"]:hover { color: white; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #238636; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTORES DE CÁLCULO ---
def dcf_model(fcf, growth, wacc, terminal, years=10):
    projs = [fcf * (1 + growth)**i for i in range(1, years + 1)]
    pv = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + terminal)) / (wacc - terminal)
    return (pv + (tv / (1 + wacc)**years)) / 0.443

def black_scholes(S, K, T, r, sigma, type='call'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if type == 'call':
        p = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        p = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
    return p, delta

# --- INTERFAZ PRINCIPAL ---
def main():
    st.title("🏛️ COST Institutional Intelligence Terminal")
    st.markdown("---")

    # --- SIDEBAR: DATOS MAESTROS ---
    st.sidebar.header("🕹️ Configuración Global")
    precio_actual = st.sidebar.number_input("Precio COST Actual ($)", value=850.0)
    
    st.sidebar.subheader("🌍 Entorno Macroeconómico")
    pib = st.sidebar.slider("Crecimiento PIB (%)", -5.0, 5.0, 2.1)
    desempleo = st.sidebar.slider("Tasa de Desempleo (%)", 3.0, 12.0, 4.2)
    
    st.sidebar.subheader("🦢 Eventos Cisne Negro")
    swan_risk = 0
    if st.sidebar.checkbox("Colapso Logístico"): swan_risk += 0.03
    if st.sidebar.checkbox("Shock Energético"): swan_risk += 0.02
    if st.sidebar.checkbox("Guerra Comercial"): swan_risk += 0.04

    # --- LÓGICA DE AJUSTE MACRO ---
    wacc_adj = 0.08 + (abs(min(0, pib))/50) + swan_risk
    growth_adj = 0.09 + (pib/100) - (desempleo/200) - (swan_risk/2)

    # --- TABS ---
    tabs = st.tabs(["💎 DCF & Monte Carlo", "👥 Peers & Market", "🌪️ Stress Test", "📉 Options Master"])

    # --- TAB 1: VALORACIÓN AVANZADA ---
    with tabs[0]:
        st.header("Valoración Intrínseca y Probabilidad")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.metric("Valor Justo (Ajustado)", f"${dcf_model(9.5, growth_adj, wacc_adj, 0.025):.2f}")
            st.info("💡 El modelo ajusta el crecimiento y el riesgo según tus inputs macro en tiempo real.")
            
        with c2:
            st.subheader("Simulación de Monte Carlo (1,000 escenarios)")
            # Generar 1000 escenarios variando crecimiento y WACC
            sims = [dcf_model(9.5, np.random.normal(growth_adj, 0.02), np.random.normal(wacc_adj, 0.01), 0.025) for _ in range(1000)]
            fig_dist = px.histogram(sims, nbins=50, title="Distribución de Probabilidad del Precio", template="plotly_dark", color_discrete_sequence=['#238636'])
            fig_dist.add_vline(x=precio_actual, line_color="red", line_dash="dash", annotation_text="Precio Actual")
            st.plotly_chart(fig_dist, use_container_width=True)
            

    # --- TAB 2: PEERS & MARKET ---
    with tabs[1]:
        st.header("Análisis de Mercado & Benchmarking")
        idx = st.selectbox("Índice de Referencia", ["S&P 500", "NASDAQ 100", "Dow Jones"])
        peers = st.multiselect("Seleccionar Pares", ["WMT", "TGT", "BJ", "TESCO", "AMZN"], default=["WMT", "TGT"])
        
        # Datos dinámicos
        peer_data = {'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'TESCO', 'AMZN'], 
                     'PE': [52.4, 31.2, 17.5, 21.1, 14.5, 45.0],
                     'Crecimiento': [9.5, 6.2, 4.5, 8.2, 3.1, 12.0]}
        df = pd.DataFrame(peer_data)
        df_filtered = df[df['Ticker'].isin(['COST'] + peers)]
        
        fig_peers = px.scatter(df_filtered, x="Crecimiento", y="PE", text="Ticker", size="PE", color="Ticker", template="plotly_dark")
        st.plotly_chart(fig_peers, use_container_width=True)
        

    # --- TAB 3: STRESS TEST ---
    with tabs[2]:
        st.header("Matriz de Resiliencia ante Crisis")
        st.warning(f"Escenario Actual: PIB {pib}% | Desempleo {desempleo}% | Riesgo Cisne +{swan_risk*100}%")
        
        # Heatmap de Sensibilidad
        wacc_s = np.linspace(wacc_adj-0.02, wacc_adj+0.02, 5)
        g_s = np.linspace(growth_adj-0.02, growth_adj+0.02, 5)
        matrix = [[dcf_model(9.5, g, w, 0.025) for g in g_s] for w in wacc_s]
        
        fig_heat = px.imshow(matrix, x=[f"g:{g*100:.1f}%" for g in g_s], y=[f"WACC:{w*100:.1f}%" for w in wacc_s],
                             text_auto='.0f', color_continuous_scale='RdYlGn', title="Sensibilidad del Precio")
        st.plotly_chart(fig_heat, use_container_width=True)

    # --- TAB 4: OPTIONS ---
    with tabs[3]:
        st.header("Estrategia de Cobertura y Apalancamiento")
        st.info("💡 Usa Calls si el Monte Carlo muestra alta probabilidad alcista. Usa Puts si el Stress Test es crítico.")
        
        o1, o2 = st.columns(2)
        with o1:
            strike = st.number_input("Strike Price", value=float(np.round(precio_actual*1.05,0)))
            iv = st.slider("Volatilidad Implícita (%)", 10, 100, 30) / 100
            tipo = st.radio("Tipo", ["Call", "Put"])
        
        opt_p, delta = black_scholes(precio_actual, strike, 30/365, 0.05, iv, tipo.lower())
        
        with o2:
            st.metric(f"Precio Teórico {tipo}", f"${opt_p:.2f}")
            st.metric("Delta (Probabilidad)", f"{abs(delta)*100:.1f}%")
            

if __name__ == "__main__":
    main()