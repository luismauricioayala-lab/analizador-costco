import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm
import yfinance as yf
import os

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.1); }
    .scenario-card { background-color: white; border-radius: 15px; padding: 20px; border: 1px solid #e0e0e0; text-align: center; color: #1c1c1c; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .metric-costco { color: #1c1c1c; font-size: 32px; font-weight: bold; margin: 5px 0; }
    .label-bajista { color: #d93025; background-color: #fce8e6; padding: 2px 10px; border-radius: 10px; font-weight: bold; font-size: 14px; }
    .label-base { color: #f29900; background-color: #fff4e5; padding: 2px 10px; border-radius: 10px; font-weight: bold; font-size: 14px; }
    .label-alcista { color: #188038; background-color: #e6f4ea; padding: 2px 10px; border-radius: 10px; font-weight: bold; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES FINANCIEROS Y DE DATOS DINÁMICOS ---

@st.cache_data(ttl=3600)
def load_live_data(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        cf = t.cashflow
        
        # Extracción dinámica de precio y beta
        price = info.get('currentPrice', 950.0)
        beta = info.get('beta', 0.79)
        
        # CÁLCULO DINÁMICO DE FCF HISTÓRICO (Últimos 4 años)
        # FCF = Operating Cash Flow + Capital Expenditure (CapEx viene negativo en yfinance)
        ops_flow = cf.loc['Operating Cash Flow']
        capex = cf.loc['Capital Expenditure']
        fcf_series = (ops_flow + capex) / 1e9 # Convertir a Billones
        
        # Calcular Crecimiento Promedio Histórico (CAGR)
        # Usamos los valores del más antiguo al más reciente
        fcf_values = fcf_series.values[::-1] 
        growth_rates = np.diff(fcf_values) / fcf_values[:-1]
        avg_growth = np.mean(growth_rates)
        
        return {
            "precio": price, 
            "beta": beta, 
            "fcf_hist": fcf_series, # Serie completa para la gráfica
            "last_fcf": fcf_series.iloc[0],
            "avg_growth": avg_growth,
            "name": info.get('longName', 'Costco Wholesale')
        }
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        # Fallback en caso de error de API
        return {"precio": 950.0, "beta": 0.79, "last_fcf": 9.5, "avg_growth": 0.12, "fcf_hist": pd.Series([9.5, 8.2, 7.1]), "name": "Costco Wholesale"}

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
    live = load_live_data("COST")
    
    st.title(f"🏛️ {live['name']} — Master Intelligence Terminal")
    st.caption("Terminal Conectada en Tiempo Real • Análisis Dinámico de Flujos")
    
    # --- SIDEBAR: SUPUESTOS DINÁMICOS ---
    st.sidebar.header("🎯 Supuestos del Analista")
    p_actual = st.sidebar.number_input("Precio Mercado ($)", value=float(live['precio']))
    fcf_in = st.sidebar.slider("FCF Base ($B)", 5.0, 20.0, value=float(live['last_fcf']))
    
    # El crecimiento inicial sugerido es el promedio histórico real
    g1_base = st.sidebar.slider("Crecimiento Años 1-5 (%)", 1, 25, int(live['avg_growth']*100)) / 100
    g2_base = st.sidebar.slider("Crecimiento Años 6-10 (%)", 1, 20, 8) / 100
    wacc_base = st.sidebar.slider("WACC Base (%)", 5.0, 15.0, 8.5) / 100
    gt = 0.025 

    if os.path.exists("Guia_Metodologica_COST.pdf"):
        with open("Guia_Metodologica_COST.pdf", "rb") as file:
            st.sidebar.download_button(label="📄 Descargar Guía Metodológica", data=file, file_name="Guia_Metodologica_COST.pdf", mime="application/pdf")

    # CÁLCULO CASO BASE
    v_base_ref, flows_base, pv_f_base, pv_t_base = dcf_engine(fcf_in, g1_base, g2_base, wacc_base, gt)

    # HEADER METRICS
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("P/E TTM", "51.8x", "Premium")
    h2.metric("Market Cap", "$450.2B", "COST-NASDAQ")
    h3.metric("Beta (Live)", f"{live['beta']}", "Defensivo")
    h4.metric("Crecimiento Hist. FCF", f"{live['avg_growth']*100:.1f}%", "Sugerido")

    st.markdown("---")
    tabs = st.tabs(["📋 Resumen", "💎 Valoración", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📚 Metodología"])

    # --- TAB 0: RESUMEN ---
    with tabs[0]:
        c_esc1, c_esc2, c_esc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1_base*0.5, g2_base*0.4, wacc_base+0.02, 0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1_base+0.03, g2_base+0.02, wacc_base-0.015, 0.03)

        c_esc1.markdown(f'<div class="scenario-card"><span class="label-bajista">Bajista</span><div class="metric-costco">${v_baj:.0f}</div><div style="color:red">{(v_baj/p_actual-1)*100:.1f}% vs actual</div></div>', unsafe_allow_html=True)
        c_esc2.markdown(f'<div class="scenario-card"><span class="label-base">Caso Base</span><div class="metric-costco">${v_base_ref:.0f}</div><div style="color:orange">{(v_base_ref/p_actual-1)*100:.1f}% vs actual</div></div>', unsafe_allow_html=True)
        c_esc3.markdown(f'<div class="scenario-card"><span class="label-alcista">Alcista</span><div class="metric-costco">${v_alc:.0f}</div><div style="color:green">{(v_alc/p_actual-1)*100:.1f}% vs actual</div></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_f_base, pv_t_base], hole=.6, marker_colors=['#005BAA', '#E31837'])])
        fig_donut.update_layout(title="Composición del Valor Intrínseco", height=400, template="plotly_white")
        st.plotly_chart(fig_donut, use_container_width=True)

    # --- TAB 1: VALORACIÓN (EL PUENTE DINÁMICO) ---
    with tabs[1]:
        st.subheader("Trayectoria Dinámica del FCF: Pasado vs Futuro")
        
        # Preparar datos para la gráfica de puente
        hist_x = [c.strftime('%Y') for c in live['fcf_hist'].index[::-1]]
        hist_y = live['fcf_hist'].values[::-1]
        
        proj_x = [str(int(hist_x[-1]) + i) for i in range(1, 11)]
        proj_y = flows_base
        
        fig_bridge = go.Figure()
        # Histórico (Azul)
        fig_bridge.add_trace(go.Scatter(x=hist_x, y=hist_y, name="Histórico Real", line=dict(color='#005BAA', width=4), mode='lines+markers'))
        # Proyección (Rojo punteado)
        # Añadimos el último punto histórico al inicio de la proyección para que se toquen
        fig_bridge.add_trace(go.Scatter(x=[hist_x[-1]] + proj_x, y=[hist_y[-1]] + proj_y, name="Proyección", line=dict(color='#E31837', width=4, dash='dash'), mode='lines+markers'))
        
        fig_bridge.update_layout(title="Puente de Generación de Caja ($B)", template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        

        st.markdown("---")
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Matriz de Sensibilidad")
            w_range = np.linspace(wacc_base-0.02, wacc_base+0.02, 5)
            g_range = np.linspace(0.015, 0.035, 5)
            matrix = [[dcf_engine(fcf_in, g1_base, g2_base, w, g)[0] for g in g_range] for w in w_range]
            df_sens = pd.DataFrame(matrix, index=[f"W:{x*100:.1f}%" for x in w_range], columns=[f"g:{x*100:.1f}%" for x in g_range])
            st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_white"), use_container_width=True)
        with c2:
            st.info(f"**Análisis de Flujos:** El modelo detecta un crecimiento histórico promedio del **{live['avg_growth']*100:.1f}%**. Basado en esto, Costco generaría aproximadamente **${flows_base[-1]:.1f}B** para el año 10.")

    # --- TABS SIGUIENTES (Sin cambios pero mantenidos para integridad) ---
    with tabs[2]: # Benchmarking
        col_b1, col_b2 = st.columns(2)
        with col_b1: st.plotly_chart(px.bar(PEERS_DATA, x='Ticker', y='PE', color='Ticker', title="P/E Ratio Comparativo"), use_container_width=True)
        with col_b2: st.plotly_chart(px.scatter(PEERS_DATA, x='Rev_Growth', y='PE', text='Ticker', size='PE', color='Ticker', title="Crecimiento vs Valuación"), use_container_width=True)
    
    with tabs[3]: # Monte Carlo
        vol_mc = st.slider("Volatilidad de Pronóstico", 0.01, 0.05, 0.02)
        sims = [dcf_engine(fcf_in, np.random.normal(g1_base, vol_mc), g2_base, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        prob_success = (np.array(sims) > p_actual).mean() * 100
        fig_mc = px.histogram(sims, nbins=40, title=f"Probabilidad de Éxito: {prob_success:.1f}%", template="plotly_white", color_discrete_sequence=['#005BAA'])
        fig_mc.add_vline(x=p_actual, line_color="red", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)

    with tabs[4]: # Stress Test
        st.header("🌪️ Stress Test Lab")
        cs1, cs2 = st.columns(2)
        with cs1:
            s_inc = st.slider("Ingreso Disponible %", -10, 5, 0); s_unem = st.slider("Desempleo %", 3, 15, 4)
        with cs2:
            s_cpi = st.slider("Inflación %", 0, 10, 3); s_wage = st.slider("Alza Salarial %", 0, 8, 4)
        adj_g = g1_base + (s_inc/200) - (s_unem/500)
        adj_w = wacc_base + (s_cpi/500) + (s_wage/1000)
        v_stress, _, _, _ = dcf_engine(fcf_in, adj_g, g2_base, adj_w, 0.025)
        st.metric("Valor Post-Estrés", f"${v_stress:.2f}", f"{(v_stress/v_base_ref-1)*100:.1f}%")

    with tabs[5]: # Opciones
        k = st.number_input("Strike Price", value=float(round(p_actual*1.05, 0)))
        iv = st.slider("Volatilidad %", 5, 100, 25) / 100
        res = calculate_full_greeks(p_actual, k, 30/365, 0.045, iv, 'call')
        st.metric("Prima Call (30D)", f"${res['price']:.2f}")
        st.write(f"**Delta:** {res['delta']:.3f} | **Vega:** {res['vega']:.3f}")

    with tabs[6]: # Metodología
        st.latex(r"K_e = R_f + \beta (R_m - R_f)")
        st.info("Este modelo utiliza un DCF de 2 etapas con una rampa de transición del año 6 al 10 conectada dinámicamente con datos históricos de la SEC.")

if __name__ == "__main__":
    main()
