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

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILO ELITE ---
st.set_page_config(
    page_title="COST Institutional | Bloomberg Master",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS: Glassmorphism de Alta Densidad (Bloomberg Dark Pro)
st.markdown("""
    <style>
    .main { background-color: #0b0e11; color: #e6edf3; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    
    /* Card Glassmorphism */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.5);
    }
    
    /* Estilo de Escenarios */
    .scenario-card {
        background: #1c2128;
        border-radius: 15px;
        padding: 30px;
        border: 1px solid #444c56;
        text-align: center;
        box-shadow: inset 0 0 15px rgba(255,255,255,0.02);
    }
    .price-hero { font-size: 48px; font-weight: 900; color: #ffffff; letter-spacing: -1px; }
    
    /* Badges */
    .badge { padding: 6px 16px; border-radius: 25px; font-weight: 800; font-size: 11px; text-transform: uppercase; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.15); border: 1px solid #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.15); border: 1px solid #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.15); border: 1px solid #dbab09; }

    /* Tabs Avanzados */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        height: 60px; background-color: #161b22;
        border-radius: 10px 10px 0px 0px; color: #8b949e;
        border: 1px solid #30363d; padding: 0 35px;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #005BAA !important; color: white !important;
        border-bottom: 5px solid #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES DE INTELIGENCIA DE DATOS ---

@st.cache_data(ttl=3600)
def fetch_institutional_data(ticker):
    """Extracción y normalización de estados financieros."""
    try:
        asset = yf.Ticker(ticker)
        inf = asset.info
        cf_raw = asset.cashflow
        
        # Free Cash Flow: Op. Cash Flow + CapEx (Normalizado)
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        
        # Análisis de Crecimiento Compuesto (CAGR)
        v_hist = fcf_series.values[::-1]
        cagr = (v_hist[-1]/v_hist[0])**(1/(len(v_hist)-1)) - 1 if len(v_hist) > 1 else 0.12
        
        return {
            "name": inf.get('longName', 'Costco Wholesale'),
            "price": inf.get('currentPrice', 950.0),
            "beta": inf.get('beta', 0.79),
            "fcf_now": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr_real": cagr,
            "pe": inf.get('trailingPE', 51.8),
            "mkt_cap": inf.get('marketCap', 450e9) / 1e9,
            "is": asset.financials, "bs": asset.balance_sheet, "cf": cf_raw
        }
    except Exception as e:
        st.error(f"Falla en Servidor de Datos: {e}")
        return None

def dcf_valuation(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Proyección de Flujos en 2 Etapas con Valor Terminal."""
    projs = []
    val = fcf
    for i in range(1, 11):
        val *= (1 + g1) if i <= 5 else (1 + g2)
        projs.append(val)
    
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, projs, pv_f, pv_t

def black_scholes_greeks(S, K, T, r, sigma, o_type='call'):
    """Cálculo de griegas para cobertura de carteras institucionales."""
    T = max(T, 0.0001)
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if o_type == 'call':
        p = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
        d = norm.cdf(d1)
    else:
        p = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
        d = norm.cdf(d1) - 1
    v = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    th = (-(S*norm.pdf(d1)*sigma / (2*np.sqrt(T))) - r*K*np.exp(-r*T)*norm.cdf(d1))/365
    return {"p": p, "d": d, "v": v, "t": th}

# --- 3. UI: CONSTRUCCIÓN DE LA TERMINAL ---

def main():
    # 1. CARGA DE DATOS
    with st.spinner("⚡ Sincronizando con Terminal Bloomberg..."):
        data = fetch_institutional_data("COST")
        if not data: return

    # --- SIDEBAR: PANEL DE CONTROL DINÁMICO ---
    st.sidebar.markdown("## 📟 Panel de Control")
    st.sidebar.markdown("---")
    
    # PREVENCIÓN DE VALUEERROR: Definimos límites basados en la data real
    # Si Costco crece un 38%, el slider se ajustará automáticamente a un máximo de 50%.
    fcf_limit = max(80.0, float(data['fcf_now'] * 2.5))
    g_limit = max(50.0, float(data['cagr_real'] * 150)) # Tolerancia del 50% extra
    
    spot = st.sidebar.number_input("Precio Spot ($)", value=float(data['price']))
    
    # Sliders con Clamping de Seguridad
    fcf_base = st.sidebar.slider("FCF Inicial ($B)", 0.0, fcf_limit, float(np.clip(data['fcf_now'], 0.0, fcf_limit)))
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", 0.0, g_limit, float(np.clip(data['cagr_real']*100, 0.0, g_limit))) / 100
    
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0.0, 30.0, 8.0) / 100
    wacc = st.sidebar.slider("Tasa Descuento WACC (%)", 4.0, 18.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Market Context")
    st.sidebar.info(f"Beta: {data['beta']} | P/E: {data['pe']:.1f}x")
    
    # Cálculos Maesto
    v_fair, flows, pv_cash, pv_term = dcf_engine(fcf_base, g1, g2, wacc)
    upside = (v_fair / spot - 1) * 100

    # --- UI: DASHBOARD PRINCIPAL ---
    st.title(f"🏛️ {data['name']} Institutional Terminal")
    st.markdown(f"**ID:** COST-MASTER-2026 | **Fuente:** SEC EDGAR & Nasdaq Real-Time")
    
    # Grid de Métricas Glassmorphism
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PRECIO SPOT", f"${spot:.2f}")
    c2.metric("FAIR VALUE (DCF)", f"${v_fair:.2f}", f"{upside:.1f}% Upside")
    c3.metric("BETA INSTITUCIONAL", f"{data['beta']}", "Low Risk")
    c4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- SISTEMA DE PESTAÑAS ---
    tabs = st.tabs(["📋 Executive Summary", "💎 DCF Analysis", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test Lab", "📉 Opciones Lab", "📥 Data Center"])

    with tabs[0]: # SUMMARY
        st.subheader("Modelado de Escenarios de Capital")
        r1, r2, r3 = st.columns(3)
        # Generar Escenarios
        v_baj, _, _, _ = dcf_engine(fcf_base, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_base, g1+0.04, g2+0.02, wacc-0.01)

        r1.markdown(f'<div class="scenario-card"><span class="badge bear">BEAR CASE</span><div class="price-hero">${v_baj:.0f}</div><small>Shock Consumo / Tasas +200bps</small></div>', unsafe_allow_html=True)
        r2.markdown(f'<div class="scenario-card"><span class="badge neutral">BASE CASE</span><div class="price-hero">${v_fair:.0f}</div><small>Tendencia Orgánica Costco</small></div>', unsafe_allow_html=True)
        r3.markdown(f'<div class="scenario-card"><span class="badge bull">BULL CASE</span><div class="price-hero">${v_alc:.0f}</div><small>Expansión Global / Membresía</small></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['Caja 1-10Y', 'Valor Perpetuo'], values=[pv_cash, pv_term], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=450, title="Distribución de Valor Presente")
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # DCF BRIDGE
        st.subheader("El Puente: Flujos Históricos Auditados vs Proyección")
        # Unión de series
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (10-K)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", title="Trayectoria del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        

        st.markdown("### Matriz de Sensibilidad: WACC vs Crecimiento (g)")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_base, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with tabs[2]: # BENCHMARKING
        st.subheader("Análisis de Pares Institucionales")
        peers = pd.DataFrame({'T': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0], 'Margin': [2.6, 2.4, 3.8, 1.9, 5.1]})
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='T', y='PE', color='T', title="Múltiplo P/E Comparativo", template="plotly_dark"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Margin', y='PE', text='T', size='PE', title="Rentabilidad vs Valuación", template="plotly_dark"), use_container_width=True)
        
        

    with tabs[3]: # MONTE CARLO
        st.subheader("Simulación Estocástica (1,000 Iteraciones)")
        v_mc = st.slider("Volatilidad de Supuestos (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_base, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sims) > spot).mean() * 100
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {prob_up:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=spot, line_color="#f85149", line_dash="dash", annotation_text="SPOT")
        st.plotly_chart(fig_mc, use_container_width=True)
        
        

    with tabs[4]: # STRESS TEST
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        st1, st2 = st.columns(2)
        with st1:
            s_inc = st.slider("Shock Ingreso Real %", -20, 10, 0)
            s_u = st.slider("Alza Desempleo %", 3, 20, 4)
        with st2:
            s_cpi = st.slider("Inflación CPI %", 0, 15, 3)
            s_w = st.slider("Carga Salarial %", 0, 12, 4)
        v_s, _, _, _ = dcf_engine(fcf_base, g1+(s_inc/200)-(s_u/500), g2, wacc+(s_cpi/500)+(s_w/1000))
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs BASE")

    with tabs[5]: # OPCIONES
        st.subheader("Gestión de Cobertura y Griegas")
        k_strike = st.number_input("Precio Strike", value=float(round(spot*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        grk = black_scholes_greeks(spot, k_strike, 45/365, 0.045, iv)
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Call (45D)", f"${grk['p']:.2f}"); o2.metric("Delta (Δ)", f"{grk['d']:.3f}")
        o3.metric("Vega (ν)", f"{grk['v']:.4f}"); o4.metric("Theta (θ/día)", f"${grk['t']:.2f}")
        
        

    with tabs[6]: # DATA CENTER
        st.subheader("Exportación de Reporte Institucional")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income_Statement')
            data['bs'].to_excel(wr, sheet_name='Balance_Sheet')
            data['cf'].to_excel(wr, sheet_name='Cash_Flow')
        st.download_button("💾 Descargar Master Excel (3-Statement Model)", buf.getvalue(), f"COST_Institutional_{datetime.date.today()}.xlsx")

if __name__ == "__main__":
    main()

