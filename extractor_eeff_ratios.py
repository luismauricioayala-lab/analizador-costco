import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm
import yfinance as yf
import os
import io
import datetime

# --- 1. CONFIGURACIÓN E INTERFAZ PREMIUM ---
st.set_page_config(
    page_title="COST Institutional Terminal | v4.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# UI: Estilo Bloomberg Professional (Glassmorphism & High Contrast)
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    
    /* Tarjetas de Métricas Estilo Terminal */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
    }
    
    /* Escenarios: Estilo Bloomberg Intelligence */
    .scenario-card {
        background: #1c2128;
        border-radius: 12px;
        padding: 25px;
        border: 1px solid #444c56;
        text-align: center;
        margin-bottom: 15px;
    }
    .price-tag { font-size: 42px; font-weight: 800; color: #ffffff; margin: 10px 0; }
    
    /* Etiquetas de Estado */
    .status-red { color: #f85149; background: rgba(248, 81, 73, 0.15); padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    .status-yellow { color: #dbab09; background: rgba(219, 171, 9, 0.15); padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    .status-green { color: #3fb950; background: rgba(63, 185, 80, 0.15); padding: 4px 12px; border-radius: 20px; font-weight: bold; }

    /* Pestañas (Tabs) Estilo Pro */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #161b22;
        border-radius: 8px 8px 0px 0px;
        color: #8b949e;
        border: 1px solid #30363d;
        padding: 0 25px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #005BAA !important; 
        color: white !important;
        border-bottom: 3px solid #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES FINANCIEROS Y DE DATOS ---

def secure_clamp(val, min_v, max_v):
    """Garantiza que la App NO crashee si los datos reales superan los límites del slider."""
    try:
        return float(np.clip(val, min_v, max_v))
    except:
        return min_v

@st.cache_data(ttl=3600)
def fetch_institutional_data(ticker_symbol):
    """Descarga datos dinámicos de Yahoo Finance y la SEC."""
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        cf_df = t.cashflow
        
        # FCF Dinámico: Cash from Ops + Capital Expenditure (que viene negativo)
        fcf_hist = (cf_df.loc['Operating Cash Flow'] + cf_df.loc['Capital Expenditure']) / 1e9
        
        # Análisis de Crecimiento (CAGR)
        vals = fcf_hist.values[::-1]
        cagr_real = (vals[-1]/vals[0])**(1/(len(vals)-1)) - 1 if len(vals) > 1 else 0.12
        
        return {
            "name": info.get('longName', 'Costco Wholesale'),
            "price": info.get('currentPrice', 950.0),
            "beta": info.get('beta', 0.79),
            "fcf_now": fcf_hist.iloc[0],
            "fcf_series": fcf_hist,
            "cagr_suggested": cagr_real,
            "pe_ttm": info.get('trailingPE', 51.8),
            "mkt_cap": info.get('marketCap', 450e9) / 1e9,
            "is": t.financials, "bs": t.balance_sheet, "cf": cf_df
        }
    except Exception as e:
        st.error(f"Error Crítico: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Modelo de Descuento de Flujos en 2 Etapas."""
    proj = []
    temp = fcf
    for i in range(1, 11):
        temp *= (1 + g1) if i <= 5 else (1 + g2)
        proj.append(temp)
    
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(proj, 1)])
    tv = (proj[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    
    return ((pv_f + pv_t) / shares) + cash, proj, pv_f, pv_t

def black_scholes_engine(S, K, T, r, sigma, o_type='call'):
    """Motor de Griegas para gestión de derivados."""
    T = max(T, 0.0001)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if o_type == 'call':
        p = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        d = norm.cdf(d1)
    else:
        p = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        d = norm.cdf(d1) - 1
    v = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    th = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d1))/365
    return {"p": p, "d": d, "v": v, "t": th}

# --- 3. UI: CONSTRUCCIÓN DE LA TERMINAL ---

def main():
    # Carga de Datos
    with st.spinner("Conectando con Terminal de Datos SEC..."):
        data = fetch_institutional_data("COST")
        if not data: return

    # --- SIDEBAR: PANEL DE CONTROL (BLINDADO) ---
    st.sidebar.markdown("## 📟 Panel de Control")
    st.sidebar.markdown("---")
    
    # PROTECCIÓN ANTI-VALUEERROR: Los sliders ahora son dinámicos
    spot_price = st.sidebar.number_input("Precio Spot ($)", value=float(data['price']))
    
    # Ajustamos el FCF inicial dentro de un rango seguro de 0 a 100
    fcf_val = secure_clamp(data['fcf_now'], 0.0, 100.0)
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 100.0, fcf_val)
    
    # Ajustamos el Crecimiento Sugerido dentro de un rango de 0 a 50%
    g_sug = secure_clamp(data['cagr_suggested'] * 100, 0.0, 50.0)
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", 0, 50, int(g_sug)) / 100
    
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0, 25, 8) / 100
    wacc = st.sidebar.slider("WACC / Descuento (%)", 4.0, 16.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Market Context")
    st.sidebar.info(f"Beta: {data['beta']} | P/E: {data['pe_ttm']:.1f}x")
    
    # Cálculos
    v_intrinsic, proj_flows, pv_cash, pv_term = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_intrinsic / spot_price - 1) * 100

    # --- MAIN UI: DASHBOARD ---
    st.title(f"🏛️ {data['name']} Intelligence")
    st.markdown(f"**Terminal ID:** COST-Institutional-v4 | **Status:** Datos SEC Sincronizados")
    
    # Tarjetas Principales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PRECIO SPOT", f"${spot_price:.2f}")
    c2.metric("FAIR VALUE (DCF)", f"${v_intrinsic:.2f}", f"{upside:.1f}% Upside")
    c3.metric("BETA INSTITUCIONAL", f"{data['beta']}", "Low Vol")
    c4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- SISTEMA DE PESTAÑAS (7 TABS) ---
    tabs = st.tabs(["📋 Resumen", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones Lab", "📥 Exportar"])

    with tabs[0]: # RESUMEN
        st.subheader("Simulación de Escenarios de Capital")
        r1, r2, r3 = st.columns(3)
        # Escenarios
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)

        r1.markdown(f'<div class="scenario-card"><span class="status-red">BAJISTA</span><div class="price-tag">${v_baj:.0f}</div><small>Shock Consumo / Tasas +200bps</small></div>', unsafe_allow_html=True)
        r2.markdown(f'<div class="scenario-card"><span class="status-yellow">CASO BASE</span><div class="price-tag">${v_intrinsic:.0f}</div><small>Tendencia Actual Costco</small></div>', unsafe_allow_html=True)
        r3.markdown(f'<div class="scenario-card"><span class="status-green">ALCISTA</span><div class="metric-costco">${v_alc:.0f}</div><small>Expansión Asia / Membresía</small></div>', unsafe_allow_html=True)
        
        st.markdown("### Composición de Valor Presente")
        fig_donut = go.Figure(data=[go.Pie(labels=['Caja 1-10Y', 'Valor Perpetuo'], values=[pv_cash, pv_term], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=450)
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # VALORACIÓN (BRIDGE)
        st.subheader("Puente de Datos: Histórico SEC vs Proyección")
        # Unimos histórico y futuro
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (SEC 10-K)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+proj_flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", title="Trayectoria del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        
        

        st.markdown("### Matriz de Sensibilidad: WACC vs g")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"{x*100:.1f}%" for x in wr], columns=[f"{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with tabs[2]: # BENCHMARKING
        peers = pd.DataFrame({'T': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [data['pe_ttm'], 31.2, 17.5, 21.1, 45.0], 'Margin': [2.6, 2.4, 3.8, 1.9, 5.1]})
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='T', y='PE', color='T', title="Múltiplo P/E Comparativo", template="plotly_dark"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Margin', y='PE', text='T', size='PE', title="Margen vs Valuación", template="plotly_dark"), use_container_width=True)
        

    with tabs[3]: # MONTE CARLO
        st.subheader("Distribución Estocástica de Probabilidades")
        vol_mc = st.slider("Volatilidad de Supuestos (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, vol_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sims) > spot_price).mean() * 100
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {prob_up:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=spot_price, line_color="#f85149", line_dash="dash")
        st.plotly_chart(fig_mc, use_container_width=True)
        

    with tabs[4]: # STRESS TEST
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        s1, s2 = st.columns(2)
        with s1: 
            sh_i = st.slider("Shock Ingreso Disponible %", -20, 5, 0)
            sh_u = st.slider("Alza Desempleo %", 3, 15, 4)
        with s2:
            sh_c = st.slider("Inflación CPI %", 0, 15, 3)
            sh_w = st.slider("Alza Salarial %", 0, 10, 4)
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(sh_i/200)-(sh_u/500), g2, wacc+(sh_c/500)+(sh_w/1000))
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_intrinsic-1)*100:.1f}%")

    with tabs[5]: # OPCIONES LAB
        st.subheader("Gestión de Cobertura y Griegas")
        k = st.number_input("Strike Price", value=float(round(spot_price*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        grk = black_scholes_engine(spot_price, k, 45/365, 0.045, iv)
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Call (45D)", f"${grk['p']:.2f}"); o2.metric("Delta (Δ)", f"{grk['d']:.3f}")
        o3.metric("Vega (ν)", f"{grk['v']:.4f}"); o4.metric("Theta (θ/día)", f"${grk['t']:.2f}")
        
        

    with tabs[6]: # EXPORTAR
        st.subheader("Generación de Reporte Institucional")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income_Statement')
            data['bs'].to_excel(wr, sheet_name='Balance_Sheet')
            data['cf'].to_excel(wr, sheet_name='Cash_Flow')
        st.download_button("💾 Descargar Master Excel (3-Statement Model)", buf.getvalue(), f"COST_Institutional_2026.xlsx")

if __name__ == "__main__":
    main()
