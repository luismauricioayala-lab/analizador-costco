import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm
import yfinance as yf
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Institutional Terminal Pro", layout="wide")

# Estilo Bloomberg / Dark Mode adaptable
st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.1); }
    .scenario-card { background-color: white; border-radius: 12px; padding: 15px; border: 1px solid #e0e0e0; text-align: center; color: #1c1c1c; }
    .metric-value { color: #005BAA; font-size: 28px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS EN TIEMPO REAL ---
@st.cache_data(ttl=600) # Se refresca cada 10 min
def get_everything_dynamic(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        # Traemos anuales y trimestrales para "engañar" al límite de 3 años
        cf_annual = t.cashflow
        cf_quarterly = t.quarterly_cashflow
        
        # Calculamos FCF (Op Cash Flow + CapEx)
        # Normalizamos el CapEx (yfinance a veces lo da positivo, a veces negativo)
        fcf_annual = (cf_annual.loc['Operating Cash Flow'] + cf_annual.loc['Capital Expenditure']) / 1e9
        fcf_q = (cf_quarterly.loc['Operating Cash Flow'] + cf_quarterly.loc['Capital Expenditure']) / 1e9
        
        # Unimos para tener una serie histórica más larga y dinámica
        hist_fcf = fcf_annual.sort_index()
        
        # Crecimiento CAGR real de los últimos años
        cagr = (hist_fcf.iloc[-1] / hist_fcf.iloc[0])**(1/(len(hist_fcf)-1)) - 1
        
        return {
            "price": info.get('currentPrice', 950.0),
            "beta": info.get('beta', 0.79),
            "fcf_last": fcf_annual.iloc[0], # El más reciente
            "fcf_history": hist_fcf,
            "cagr": cagr,
            "name": info.get('longName', ticker_symbol),
            "market_cap": info.get('marketCap', 0) / 1e9
        }
    except:
        return None

# --- 3. MOTOR DCF DINÁMICO ---
def run_dynamic_dcf(fcf_base, g1, g2, wacc, gt=0.025, shares=0.443):
    projections = []
    current = fcf_base
    for i in range(1, 11):
        current *= (1 + g1) if i <= 5 else (1 + g2)
        projections.append(current)
    
    # Valor Presente de los flujos
    pv_flows = sum([f / (1 + wacc)**i for i, f in enumerate(projections, 1)])
    # Valor Terminal
    tv = (projections[-1] * (1 + gt)) / (wacc - gt)
    pv_tv = tv / (1 + wacc)**10
    
    intrinsic_value = (pv_flows + pv_tv) / shares
    return intrinsic_value, projections, pv_flows, pv_tv

# --- 4. INTERFAZ PRINCIPAL ---
def main():
    st.sidebar.title("🛠️ Panel de Control")
    ticker = st.sidebar.text_input("Ticker Symbol", value="COST").upper()
    
    # CARGA DE DATOS
    data = get_everything_dynamic(ticker)
    
    if data is None:
        st.error("No se pudieron obtener datos. Revisa el Ticker.")
        return

    # SLIDERS QUE REACCIONAN A LA DATA CARGADA
    st.sidebar.markdown("---")
    st.sidebar.subheader("Variables del Modelo")
    
    # Usamos los datos reales como "Punto de Partida" de los sliders
    fcf_input = st.sidebar.slider("FCF Inicial ($B)", 1.0, 30.0, float(data['fcf_last']))
    g1_input = st.sidebar.slider("Crecimiento Años 1-5 (%)", 0, 30, int(data['cagr']*100)) / 100
    g2_input = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0, 20, 8) / 100
    wacc_input = st.sidebar.slider("WACC (%)", 5.0, 15.0, 8.5) / 100
    
    # CÁLCULO INSTANTÁNEO
    v_fair, flows, pv_f, pv_t = run_dynamic_dcf(fcf_input, g1_input, g2_input, wacc_input)
    upside = (v_fair / data['price'] - 1) * 100

    # UI PRINCIPAL
    st.title(f"🏛️ Terminal: {data['name']}")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Precio Actual", f"${data['price']:.2f}")
    m2.metric("Valor Intrínseco", f"${v_fair:.2f}", f"{upside:.1f}%")
    m3.metric("Beta", f"{data['beta']:.2,}")
    m4.metric("Market Cap", f"${data['market_cap']:.1f}B")

    st.markdown("---")
    
    # TABS DINÁMICOS
    tab_val, tab_hist, tab_mc = st.tabs(["💎 Valoración en Vivo", "📜 Histórico Real", "🎲 Monte Carlo"])

    with tab_val:
        st.subheader("Proyección Dinámica a 10 Años")
        # Gráfica de Proyección
        años = [f"Año {i}" for i in range(1, 11)]
        fig_proj = px.area(x=años, y=flows, title="Flujo de Caja Libre Proyectado ($B)",
                           labels={'x': 'Horizonte', 'y': 'FCF ($B)'},
                           color_discrete_sequence=['#005BAA'])
        fig_proj.update_layout(template="plotly_white")
        st.plotly_chart(fig_proj, use_container_width=True)
        

    with tab_hist:
        st.subheader("El 'Bridge' de los 3 Años (Data Real vs Proyectada)")
        # Unimos lo que nos dio Yahoo con tu proyección actual
        hist_x = [d.strftime('%Y') for d in data['fcf_history'].index]
        hist_y = data['fcf_history'].values
        
        proj_x = [str(int(hist_x[-1]) + i) for i in range(1, 6)]
        proj_y = flows[:5]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=hist_x, y=hist_y, name="Histórico (Yahoo)", line=dict(color='#005BAA', width=4)))
        fig_bridge.add_trace(go.Scatter(x=[hist_x[-1]]+proj_x, y=[hist_y[-1]]+proj_y, name="Tu Proyección", 
                                        line=dict(color='#E31837', dash='dash', width=4)))
        
        fig_bridge.update_layout(title="Conexión de Flujos Reales y Estimados", template="plotly_white")
        st.plotly_chart(fig_bridge, use_container_width=True)
        

    with tab_mc:
        st.subheader("Simulación de Probabilidades")
        # Corremos 500 simulaciones cada vez que se mueve un slider
        sims = []
        for _ in range(500):
            s_g1 = np.random.normal(g1_input, 0.02)
            s_w = np.random.normal(wacc_input, 0.005)
            val, _, _, _ = run_dynamic_dcf(fcf_input, s_g1, g2_input, s_w)
            sims.append(val)
        
        fig_hist = px.histogram(sims, nbins=30, title="Distribución de Valor Intrínseco",
                                color_discrete_sequence=['#188038'], template="plotly_white")
        fig_hist.add_vline(x=data['price'], line_color="red", line_dash="dash", annotation_text="Precio Mercado")
        st.plotly_chart(fig_hist, use_container_width=True)
        

if __name__ == "__main__":
    main()
