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
    page_title="COST Master Terminal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. UI: CSS DE ALTA FIDELIDAD (ESTILO BLOOMBERG / GLASS) ---
st.markdown("""
    <style>
    /* Fondo General Profundo */
    .main { background-color: #0b0e11; color: #e6edf3; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    [data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #30363d; }
    
    /* Tarjetas de Métricas Institucionales */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #58a6ff;
        background: rgba(88, 166, 255, 0.05);
    }
    
    /* Diseño de Escenarios */
    .scenario-card {
        background: #161b22;
        border-radius: 15px;
        padding: 30px;
        border: 1px solid #30363d;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    .price-hero { font-size: 44px; font-weight: 900; color: #ffffff; letter-spacing: -1.5px; margin: 10px 0; }
    
    /* Badges de Estado */
    .status-badge { padding: 5px 15px; border-radius: 20px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.1); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.1); border-color: #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.1); border-color: #dbab09; }

    /* Custom Tabs Pro */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 55px; background-color: #161b22;
        border-radius: 10px 10px 0px 0px; color: #8b949e;
        border: 1px solid #30363d; padding: 0 25px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #005BAA !important; color: white !important;
        border-bottom: 4px solid #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO (UNIFICADOS) ---

def secure_clamp(val, min_v, max_v):
    """Protección total contra ValueError en Sliders."""
    try:
        return float(np.clip(val, min_v, max_v))
    except:
        return min_v

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    """Motor de extracción SEC/Yahoo Finance."""
    try:
        asset = yf.Ticker(ticker_symbol)
        info = asset.info
        cf_raw = asset.cashflow
        
        # Free Cash Flow Normalizado (Billones)
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
        st.error(f"Falla de Conexión: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Motor DCF Unificado (Referenciado correctamente en main)."""
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
    """Motor de Griegas Institucional."""
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
    with st.spinner("⚡ Conectando a Terminal Bloomberg Pro..."):
        data = load_institutional_data("COST")
        if not data: return

    # --- SIDEBAR: CONTROL ELÁSTICO (SOLUCIONA EL VALUEERROR) ---
    st.sidebar.markdown("## ⚙️ Panel de Control")
    st.sidebar.markdown("---")
    
    # Ajuste dinámico de límites para evitar crasheos
    fcf_limit = max(100.0, float(data['fcf_now'] * 2.5))
    g_limit = max(60.0, float(data['cagr_real'] * 160)) 
    
    p_mkt = st.sidebar.number_input("Precio Spot ($)", value=float(data['price']))
    
    # Sliders Blindados con secure_clamp
    f_val = secure_clamp(data['fcf_now'], 0.0, fcf_limit)
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, fcf_limit, f_val)
    
    g_val = secure_clamp(data['cagr_real'] * 100, 0.0, g_limit)
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", 0, int(g_limit), int(g_val)) / 100
    
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0, 30, 8) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 3.0, 18.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"Beta: {data['beta']} | PE: {data['pe']:.1f}x")
    
    # 2. CÁLCULO CORE (REFERENCIADO CORRECTAMENTE)
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # --- UI: DASHBOARD PRINCIPAL ---
    st.title(f"🏛️ {data['name']} Intelligence")
    st.caption(f"Terminal ID: COST-2026-PRO | Status: Datos SEC Sincronizados")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PRECIO SPOT", f"${p_mkt:.2f}")
    col2.metric("FAIR VALUE", f"${v_fair:.2f}", f"{upside:.1f}% Upside")
    col3.metric("RIESGO BETA", f"{data['beta']}", "Defensivo")
    col4.metric("MARKET CAP", f"${data['mkt_cap']:.1f}B")

    st.markdown("---")
    
    # --- SISTEMA DE PESTAÑAS (7 TABS COMPLETOS) ---
    tabs = st.tabs(["📋 Resumen", "💎 Valoración", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📥 Exportar"])

    with tabs[0]: # RESUMEN
        c1, c2, c3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)

        c1.markdown(f'<div class="scenario-card"><span class="status-badge bear">BAJISTA</span><div class="price-hero">${v_baj:.0f}</div><small>Shock Consumo / Tasas +200bps</small></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="scenario-card"><span class="status-badge neutral">CASO BASE</span><div class="price-hero">${v_fair:.0f}</div><small>Tendencia Orgánica Costco</small></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="scenario-card"><span class="status-badge bull">ALCISTA</span><div class="price-hero">${v_alc:.0f}</div><small>Expansión Asia / Membresía</small></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'PV Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#C1D82F'])])
        fig_donut.update_layout(template="plotly_dark", height=450, title="Distribución del Valor Intrínseco")
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # VALORACIÓN BRIDGE
        st.subheader("Puente de Datos: Pasado Auditado vs Proyección")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (10-K)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        fig_bridge.update_layout(template="plotly_dark", title="Trayectoria del Free Cash Flow ($B)", hovermode="x unified")
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        
        

        st.markdown("### Matriz de Sensibilidad: WACC vs g")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

    with tabs[2]: # BENCHMARKING
        peers = pd.DataFrame({'T': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0], 'Margin': [2.6, 2.4, 3.8, 1.9, 5.1]})
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers, x='T', y='PE', color='T', title="Múltiplo P/E Relativo", template="plotly_dark"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers, x='Margin', y='PE', text='T', size='PE', title="Rentabilidad vs Valuación", template="plotly_dark"), use_container_width=True)
        

    with tabs[3]: # MONTE CARLO
        st.subheader("Distribución Estocástica de Probabilidades (1,000 Simulaciones)")
        v_mc = st.slider("Incertidumbre de Pronóstico (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sims) > p_mkt).mean() * 100
        fig_mc = px.histogram(sims, nbins=60, title=f"Probabilidad de Upside: {prob_up:.1f}%", template="plotly_dark", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="#f85149", line_dash="dash", annotation_text="SPOT")
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
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(s_inc/200)-(s_u/500), g2, wacc+(s_cpi/500)+(s_w/1000))
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}%")

    with tabs[5]: # OPCIONES
        st.subheader("Gestión de Cobertura y Griegas")
        k_s = st.number_input("Strike Price", value=float(round(p_mkt*1.05, 0)))
        iv = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        grk = black_scholes_engine(p_mkt, k_s, 45/365, 0.045, iv)
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
        st.download_button("💾 Descargar Master Excel (3-Statement Model)", buf.getvalue(), f"COST_Institutional_Model.xlsx")

if __name__ == "__main__":
    main()
