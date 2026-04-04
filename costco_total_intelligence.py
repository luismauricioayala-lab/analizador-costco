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

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="COST Institutional Master",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. UI: CSS ADAPTATIVO (SOPORTE LIGHT/DARK MODE) ---
st.markdown("""
    <style>
    /* VARIABLES DINÁMICAS BASADAS EN EL TEMA DE STREAMLIT */
    :root {
        --card-bg: var(--secondary-background-color);
        --border-color: var(--border-color);
        --text-main: var(--text-color);
    }

    /* Contenedor Principal */
    .main { 
        padding-top: 2rem;
    }

    /* Tarjetas de Métricas Adaptativas */
    div[data-testid="stMetric"] {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }

    /* Fix para el texto de métricas */
    div[data-testid="stMetric"] label { color: var(--text-main) !important; font-weight: 600 !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: var(--text-main) !important; font-size: 2.5rem !important; font-weight: 800 !important; }

    /* Tarjetas de Escenarios (Glassmorphism Inteligente) */
    .scenario-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 15px;
        padding: 30px;
        text-align: center;
        margin-bottom: 20px;
    }
    .price-hero { 
        font-size: 42px; 
        font-weight: 900; 
        color: var(--primary-color); 
        letter-spacing: -1.5px; 
        margin: 10px 0; 
    }
    
    /* Badges de Upside/Downside */
    .badge { padding: 5px 12px; border-radius: 15px; font-weight: 700; font-size: 12px; display: inline-block; margin-bottom: 10px; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.15); border: 1px solid #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.15); border: 1px solid #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.15); border: 1px solid #dbab09; }

    /* Pestañas (Tabs) Estilo Institucional */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--card-bg);
        border-radius: 8px 8px 0px 0px;
        color: var(--text-main);
        border: 1px solid var(--border-color);
        padding: 0 25px;
        height: 50px;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #005BAA !important; 
        color: white !important;
        border: 1px solid #005BAA !important;
    }

    /* Ajuste para Sidebar */
    section[data-testid="stSidebar"] {
        border-right: 1px solid var(--border-color);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO (BLINDADOS) ---

def secure_clamp(val, min_v, max_v):
    """Garantiza que el valor esté estrictamente dentro del rango del slider."""
    return float(max(min(val, max_v), min_v))

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    try:
        asset = yf.Ticker(ticker_symbol)
        info = asset.info
        cf_raw = asset.cashflow
        
        # Free Cash Flow: Op. Cash Flow + CapEx
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        
        # CAGR Histórico Real
        v_hist = fcf_series.values[::-1]
        cagr = (v_hist[-1]/v_hist[0])**(1/(len(v_hist)-1)) - 1 if len(v_hist) > 1 else 0.12
        
        return {
            "name": info.get('longName', 'Costco Wholesale'),
            "price": info.get('currentPrice', 950.0),
            "beta": info.get('beta', 0.79),
            "fcf_now": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr_real": cagr,
            "pe": info.get('trailingPE', 51.8),
            "mkt_cap": info.get('marketCap', 450e9) / 1e9,
            "is": asset.financials, "bs": asset.balance_sheet, "cf": cf_raw
        }
    except Exception as e:
        st.error(f"Falla de Sincronización: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Modelo de Valoración de 2 Etapas."""
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
    """Motor de Derivados Institucional."""
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

# --- 4. LÓGICA PRINCIPAL (MAIN) ---

def main():
    # 1. CARGA DE DATOS
    with st.spinner("🏛️ Sincronizando Terminal Institucional..."):
        data = load_institutional_data("COST")
        if not data: return

    # --- SIDEBAR: PANEL DE CONTROL (BLINDADO) ---
    st.sidebar.markdown("## 📟 Dashboard Control")
    st.sidebar.markdown("---")
    
    # Pre-cálculo de límites dinámicos para evitar ValueError
    fcf_limit = float(max(100.0, data['fcf_now'] * 2.5))
    g_limit = float(max(60.0, data['cagr_real'] * 200.0))
    
    p_mkt = st.sidebar.number_input("Precio Spot de Mercado ($)", value=float(data['price']))
    
    # Sliders Elásticos con secure_clamp
    f_init = secure_clamp(data['fcf_now'], 0.0, fcf_limit)
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, fcf_limit, f_init)
    
    g_init = secure_clamp(data['cagr_real'] * 100, 0.0, g_limit)
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", 0, int(g_limit), int(g_init)) / 100
    
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0, 30, 8) / 100
    wacc = st.sidebar.slider("Tasa de Descuento (WACC) %", 3.0, 18.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"PE TTM: {data['pe']:.1f}x | Beta: {data['beta']}")

    # 2. CÁLCULOS CENTRALES
    v_intrinsic, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_intrinsic / p_mkt - 1) * 100

    # --- UI: DASHBOARD ---
    st.title(f"🏛️ {data['name']} Intelligence")
    st.caption(f"Terminal ID: COST-2026-HYBRID | SEC Data Connected")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PRECIO SPOT", f"${p_mkt:.2f}")
    
    # Color de upside adaptativo
    u_color = "normal" if upside > 0 else "inverse"
    col2.metric("FAIR VALUE (DCF)", f"${v_intrinsic:.2f}", f"{upside:.1f}% Upside", delta_color=u_color)
    
    col3.metric("RIESGO BETA", f"{data['beta']}", "Defensivo")
    col4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- TABS ADAPTATIVOS ---
    tabs = st.tabs(["📋 Resumen", "💎 Valoración Pro", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones Lab", "📥 Exportar"])

    with tabs[0]: # SUMMARY
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)

        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">BEAR CASE</span><div class="price-hero">${v_baj:.0f}</div><small>Shock Consumo / Tasas +200bps</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">BASE CASE</span><div class="price-hero">${v_intrinsic:.0f}</div><small>Current Strategy</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">BULL CASE</span><div class="price-hero">${v_alc:.0f}</div><small>Expansión Asia / Membresía</small></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['Cash Flow 10Y', 'Valor Perpetuo'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_white" if upside > 0 else "plotly_dark", height=450, title="Estructura de Valor Intrínseco")
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # DCF BRIDGE
        st.subheader("Puente de Flujos: Histórico Auditado vs Forecast")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (10-K)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(title="Trayectoria del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        st.markdown("### Matriz de Sensibilidad")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn'), use_container_width=True)

    with tabs[2]: # BENCHMARKING
        peers = pd.DataFrame({'T': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0], 'Margin': [2.6, 2.4, 3.8, 1.9, 5.1]})
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='T', y='PE', color='T', title="Múltiplo P/E Relativo"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Margin', y='PE', text='T', size='PE', title="Márgenes vs Valuación"), use_container_width=True)
        
    with tabs[3]: # MONTE CARLO
        st.subheader("Distribución de Probabilidades Monte Carlo")
        v_mc = st.slider("Incertidumbre de Pronóstico (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sims) > p_mkt).mean() * 100
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {prob_up:.1f}%", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="red", line_dash="dash", annotation_text="SPOT")
        st.plotly_chart(fig_mc, use_container_width=True)
        
    with tabs[4]: # STRESS TEST
        st.subheader("🌪️ Laboratorio de Stress Macroeconómico")
        s1, s2 = st.columns(2)
        with s1:
            sh_i = st.slider("Shock Ingreso Real %", -20, 10, 0)
            sh_u = st.slider("Alza Desempleo %", 3, 15, 4)
        with s2:
            sh_c = st.slider("Inflación CPI %", 0, 15, 3)
            sh_w = st.slider("Alza Salarial %", 0, 10, 4)
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(sh_i/200)-(sh_u/500), g2, wacc+(sh_c/500)+(sh_w/1000))
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_intrinsic-1)*100:.1f}% vs BASE")

    with tabs[5]: # OPCIONES LAB
        st.subheader("Análisis de Griegas y Cobertura")
        k_s = st.number_input("Strike Price Ref.", value=float(round(p_mkt*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        grk = black_scholes_greeks(p_mkt, k_s, 45/365, 0.045, iv)
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Estimada", f"${grk['p']:.2f}")
        o2.metric("Delta (Δ)", f"{grk['d']:.3f}")
        o3.metric("Vega (ν)", f"{grk['v']:.4f}")
        o4.metric("Theta (θ/día)", f"${grk['t']:.2f}")
        
    with tabs[6]: # EXPORTAR
        st.subheader("Generación de Reporte Institucional")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income'); data['bs'].to_excel(wr, sheet_name='Balance'); data['cf'].to_excel(wr, sheet_name='CashFlow')
        st.download_button("💾 Descargar Master Excel (3-Statement)", buf.getvalue(), f"COST_Institutional_Model.xlsx")

if __name__ == "__main__":
    main()
