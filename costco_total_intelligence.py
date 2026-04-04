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

# --- 2. UI: CSS DE ALTA FIDELIDAD ---
st.markdown("""
    <style>
    .main { background-color: #0b0e11; color: #e6edf3; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #30363d; }
    
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 22px;
        border-radius: 12px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
    }
    
    .scenario-card {
        background: #161b22;
        border-radius: 15px;
        padding: 30px;
        border: 1px solid #30363d;
        text-align: center;
    }
    .price-hero { font-size: 46px; font-weight: 900; color: #ffffff; letter-spacing: -1.5px; margin: 12px 0; }
    
    .badge { padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 11px; text-transform: uppercase; border: 1px solid; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.1); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.1); border-color: #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.1); border-color: #dbab09; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 55px; background-color: #161b22;
        border-radius: 10px 10px 0px 0px; color: #8b949e;
        border: 1px solid #30363d; padding: 0 30px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #005BAA !important; color: white !important;
        border-bottom: 4px solid #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO ---

def secure_clamp(val, min_v, max_v):
    """Garantiza que el valor esté estrictamente dentro del rango del slider."""
    return float(max(min(val, max_v), min_v))

@st.cache_data(ttl=3600)
def load_terminal_data(ticker_symbol):
    try:
        asset = yf.Ticker(ticker_symbol)
        info = asset.info
        cf_raw = asset.cashflow
        
        # FCF: Op Cash Flow + CapEx (en Billones)
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        
        # CAGR Histórico
        v_hist = fcf_series.values[::-1]
        if len(v_hist) > 1 and v_hist[0] > 0:
            cagr = (v_hist[-1]/v_hist[0])**(1/(len(v_hist)-1)) - 1
        else:
            cagr = 0.12
        
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
        st.error(f"Error de Datos: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Modelo DCF de 2 Etapas."""
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

def black_scholes_engine(S, K, T, r, sigma, o_type='call'):
    """Griegas Institucionales."""
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

# --- 4. LÓGICA PRINCIPAL ---

def main():
    with st.spinner("⚡ Conectando a Terminal Bloomberg Pro..."):
        data = load_terminal_data("COST")
        if not data: return

    # --- SIDEBAR: FIX DEFINITIVO VALUEERROR ---
    st.sidebar.markdown("## 📟 Dashboard Control")
    st.sidebar.markdown("---")
    
    # Definimos rangos fijos extremadamente amplios para que NADA se salga
    MIN_FCF, MAX_FCF = -10.0, 150.0
    MIN_G, MAX_G = -50, 150
    
    p_mkt = st.sidebar.number_input("Precio Spot ($)", value=float(data['price']))
    
    # Aplicamos Clamping ANTES de crear el slider
    fcf_init = secure_clamp(data['fcf_now'], MIN_FCF, MAX_FCF)
    fcf_in = st.sidebar.slider("FCF Base ($B)", MIN_FCF, MAX_FCF, fcf_init)
    
    g_init = secure_clamp(data['cagr_real'] * 100, float(MIN_G), float(MAX_G))
    g1 = st.sidebar.slider("Crecimiento Años 1-5 (%)", MIN_G, MAX_G, int(g_init)) / 100
    
    g2 = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0, 50, 8) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 2.0, 20.0, 8.5) / 100
    
    # 2. CÁLCULO CORE
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # --- UI: DASHBOARD ---
    st.title(f"🏛️ {data['name']} Intelligence")
    st.caption(f"Terminal ID: COST-MASTER-v7.5 | Status: Real-Time SEC Stream")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PRECIO SPOT", f"${p_mkt:.2f}")
    col2.metric("FAIR VALUE (DCF)", f"${v_fair:.2f}", f"{upside:.1f}% Upside")
    col3.metric("BETA (RIESGO)", f"{data['beta']}", "Low Vol")
    col4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    tabs = st.tabs(["📋 Resumen", "💎 Valoración", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📥 Exportar"])

    with tabs[0]: # SUMMARY
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)

        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">BAJISTA</span><div class="price-hero">${v_baj:.0f}</div><small>Shock Consumo / Tasas +200bps</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">BASE CASE</span><div class="price-hero">${v_fair:.0f}</div><small>Tendencia Orgánica Costco</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">ALCISTA</span><div class="price-hero">${v_alc:.0f}</div><small>Expansión Asia / Membresía</small></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'PV Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=450, title="Distribución de Valor")
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # VALORACIÓN BRIDGE
        st.subheader("Trayectoria de Generación de Caja: Histórico SEC vs Proyección")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Auditado (10-K)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Estimado", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", title="Free Cash Flow Bridge ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)

        st.markdown("### Matriz de Sensibilidad")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with tabs[2]: # BENCHMARKING
        peers = pd.DataFrame({'T': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0], 'Margin': [2.6, 2.4, 3.8, 1.9, 5.1]})
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='T', y='PE', color='T', title="Múltiplo P/E Comparativo", template="plotly_dark"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Margin', y='PE', text='T', size='PE', title="Márgenes vs Valuación", template="plotly_dark"), use_container_width=True)

    with tabs[3]: # MONTE CARLO
        st.subheader("Simulación Estocástica (1,000 Iteraciones)")
        v_mc = st.slider("Incertidumbre (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sims) > p_mkt).mean() * 100
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {prob_up:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="#f85149", line_dash="dash", annotation_text="SPOT")
        st.plotly_chart(fig_mc, use_container_width=True)

    with tabs[4]: # STRESS TEST
        st.subheader("🌪️ Laboratorio de Stress Macroeconómico")
        st1, st2 = st.columns(2)
        with st1:
            s_inc = st.slider("Shock Ingreso %", -30, 10, 0)
            s_u = st.slider("Alza Desempleo %", 3, 25, 4)
        with st2:
            s_c = st.slider("Inflación CPI %", 0, 20, 3)
            s_w = st.slider("Carga Salarial %", 0, 15, 4)
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(s_inc/200)-(s_u/500), g2, wacc+(s_c/500)+(s_w/1000))
        st.metric("Post-Stress Fair Value", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs BASE")

    with tabs[5]: # OPCIONES
        st.subheader("Análisis de Griegas")
        k_s = st.number_input("Strike Price Ref.", value=float(round(p_mkt*1.05, 0)))
        iv = st.slider("IV %", 5, 120, 25) / 100
        grk = black_scholes_engine(p_mkt, k_s, 45/365, 0.045, iv)
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Prima Call (45D)", f"${grk['p']:.2f}"); o2.metric("Delta (Δ)", f"{grk['d']:.3f}")
        o3.metric("Vega (ν)", f"{grk['v']:.4f}"); o4.metric("Theta (θ/día)", f"${grk['t']:.2f}")

    with tabs[6]: # EXPORTAR
        st.subheader("Data Center")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income'); data['bs'].to_excel(wr, sheet_name='Balance'); data['cf'].to_excel(wr, sheet_name='CashFlow')
        st.download_button("💾 Descargar Master Excel (3-Statement)", buf.getvalue(), f"COST_Model_Final.xlsx")

if __name__ == "__main__":
    main()
