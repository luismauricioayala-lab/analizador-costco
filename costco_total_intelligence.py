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

# --- 2. UI: CSS ADAPTATIVO (LIGHT/DARK) ---
st.markdown("""
    <style>
    :root {
        --text-main: var(--text-color);
        --bg-card: var(--secondary-background-color);
        --accent: #005BAA;
    }
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 20px !important;
        border-radius: 12px !important;
    }
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 15px; padding: 25px; text-align: center; margin-bottom: 20px;
    }
    .price-hero { font-size: 40px; font-weight: 900; color: var(--text-main); letter-spacing: -1px; }
    .badge { padding: 4px 12px; border-radius: 15px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; margin-bottom: 8px; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.15); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.15); border-color: #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.15); border-color: #dbab09; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); padding: 0 20px; border-radius: 8px 8px 0 0; }
    .stTabs [aria-selected="true"] { background-color: #005BAA !important; color: white !important; }
    .swan-box { border: 2px dashed #f85149; padding: 15px; border-radius: 10px; background: rgba(248, 81, 73, 0.05); margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO Y DATOS ---

def secure_clamp(val, min_v, max_v):
    """Garantiza estabilidad total en los sliders de la interfaz."""
    try:
        return float(max(min(float(val), float(max_v)), float(min_v)))
    except:
        return float(min_v)

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    try:
        asset = yf.Ticker(ticker_symbol)
        inf, cf_raw = asset.info, asset.cashflow
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        v_h = fcf_series.values[::-1]
        cagr = (v_h[-1]/v_h[0])**(1/(len(v_h)-1)) - 1 if len(v_h) > 1 and v_h[0] > 0 else 0.12
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
    except: return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    projs = [fcf * (1 + g1)**i if i <= 5 else fcf * (1 + g1)**5 * (1 + g2)**(i-5) for i in range(1, 11)]
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    return ((pv_f + pv_t) / shares) + cash, projs, pv_f, pv_t

def calculate_full_greeks(S, K, T, r, sigma, type='call'):
    T = max(T, 0.0001)
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if type == 'call':
        price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1)/(S*sigma*np.sqrt(T))
    vega = (S*np.sqrt(T)*norm.pdf(d1))/100
    theta = (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T))) - r*K*np.exp(-r*T)*norm.cdf(d2 if type=='call' else -d2))/365
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# --- 4. LÓGICA PRINCIPAL ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # --- SIDEBAR: PANEL DE CONTROL BLINDADO ---
    st.sidebar.markdown("### 📊 Supuestos del Analista")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    
    # RANGOS MASIVOS PARA EVITAR EL VALUEERROR DEFINITIVAMENTE
    MIN_FCF, MAX_FCF = -50.0, 200.0
    MIN_G, MAX_G = -50.0, 150.0
    
    fcf_in = st.sidebar.slider("FCF Base ($B)", MIN_FCF, MAX_FCF, secure_clamp(data['fcf_now'], MIN_FCF, MAX_FCF))
    g1 = st.sidebar.slider("Crecimiento Años 1-5 (%)", MIN_G, MAX_G, int(secure_clamp(data['cagr_real']*100, MIN_G, MAX_G))) / 100
    g2 = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0.0, 50.0, 8.0) / 100
    wacc = st.sidebar.slider("WACC Base (%)", 3.0, 20.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    buf_m = io.BytesIO(b"Analisis COST Master: DCF 2-Stages + Monte Carlo Simulation")
    st.sidebar.download_button("📄 Descargar Guía Metodológica", buf_m, "Metodologia_Institucional.pdf")

    # Cálculos Maesto
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # Header de Mercado
    st.title(f"🏛️ {data['name']} — Master Intelligence Terminal")
    st.caption("Terminal Conectada en Tiempo Real • Datos via Yahoo Finance & SEC")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B")
    b_label = "Neutral" if data['beta'] > 0.9 else "Defensivo"
    m3.metric("Beta (Live)", f"{data['beta']}", b_label)
    m4.metric("Valor Intrínseco", f"${v_fair:.0f}", f"{upside:.1f}% Upside", delta_color="normal" if upside > 0 else "inverse")

    st.markdown("---")
    
    tabs = st.tabs(["📋 Resumen", "💎 Valoración", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📚 Metodología", "📥 Exportar"])

    with tabs[0]: # RESUMEN
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_baj:.0f}</div><small style="color:red">{((v_baj/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">Caso Base</span><div class="price-hero">${v_fair:.0f}</div><small style="color:orange">{upside:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_alc:.0f}</div><small style="color:green">{((v_alc/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        st.plotly_chart(go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#E31837'])]), use_container_width=True)

    with tabs[1]: # VALORACIÓN + MATRIZ
        st.subheader("Trayectoria de Flujos y Sensibilidad")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (SEC)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+[str(int(h_x[-1])+i) for i in range(1,11)], y=[h_y[-1]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        st.plotly_chart(fig_bridge, use_container_width=True)

        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', title="Sensibilidad: WACC vs G Terminal"), use_container_width=True)

    with tabs[2]: # BENCHMARKING DINÁMICO Y CONSISTENTE
        st.subheader("Análisis de Pares e Índices (Live SEC Stream)")
        peer_list = ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', '^GSPC', '^IXIC']
        
        @st.cache_data(ttl=3600)
        def get_peers_advanced(tickers):
            rows = []
            for t in tickers:
                try:
                    obj = yf.Ticker(t)
                    inf = obj.info
                    name = "S&P 500" if t == '^GSPC' else "Nasdaq" if t == '^IXIC' else t
                    pe = inf.get('trailingPE', 25.0 if t=='^GSPC' else 30.0 if t=='^IXIC' else 0)
                    # Intentamos buscar crecimientos variados para que no todos sean 8%
                    growth = inf.get('earningsQuarterlyGrowth', inf.get('revenueGrowth', 0.08)) * 100
                    rows.append({'Ticker': name, 'PE': pe, 'Growth': growth})
                except: continue
            return pd.DataFrame(rows)

        df_p = get_peers_advanced(peer_list)
        b1, b2 = st.columns(2)
        # Sincronizamos paleta de colores
        palette = px.colors.qualitative.Prism
        b1.plotly_chart(px.bar(df_p, x='Ticker', y='PE', color='Ticker', title="Múltiplo P/E Live", color_discrete_sequence=palette), use_container_width=True)
        
        fig_sc = px.scatter(df_p, x='Growth', y='PE', color='Ticker', text='Ticker', size='PE', title="Crecimiento Real vs Valuación", color_discrete_sequence=palette)
        fig_sc.update_traces(textposition='top center', marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        b2.plotly_chart(fig_sc, use_container_width=True)

    with tabs[3]: # MONTE CARLO
        st.subheader("Simulación Monte Carlo (1,000 Iteraciones)")
        v_mc = st.slider("Incertidumbre (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        prob_up = (np.array(sims) > p_mkt).mean() * 100
        st.plotly_chart(px.histogram(sims, nbins=50, title=f"Probabilidad de Upside: {prob_up:.1f}%", color_discrete_sequence=['#3fb950']), use_container_width=True)

    with tabs[4]: # STRESS TEST + SWAN
        st.subheader("🌪️ Laboratorio de Stress Macroeconómico")
        st1, st2 = st.columns(2)
        with st1: sh_i = st.slider("Shock Ingreso %", -25, 10, 0); sh_u = st.slider("Alza Desempleo %", 3, 20, 4)
        with st2: sh_c = st.slider("Inflación CPI %", 0, 15, 3); sh_w = st.slider("Alza Salarial %", 0, 12, 4)
        
        st.markdown('<div class="swan-box">### ⚠️ Cisnes Negros', unsafe_allow_html=True)
        sw1, sw2, sw3 = st.columns(3)
        g_sw, w_sw = 0, 0
        if sw1.checkbox("Guerra / Conflicto"): g_sw -= 0.06; w_sw += 0.025
        if sw2.checkbox("Crisis Logística"): g_sw -= 0.03; w_sw += 0.01
        if sw3.checkbox("Ciberataque"): g_sw -= 0.04; w_sw += 0.015
        st.markdown('</div>', unsafe_allow_html=True)
            
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(sh_i/200)-(sh_u/500)+g_sw, g2, wacc+(sh_c/500)+(sh_w/1000)+w_sw)
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs BASE")

    with tabs[5]: # OPCIONES + GRIEGOS
        st.subheader("Griegas Black-Scholes")
        ko1, ko2 = st.columns(2)
        with ko1: k_s = st.number_input("Strike Price Ref.", value=float(round(p_mkt*1.05, 0)))
        with ko2: vol_o = st.slider("Volatilidad Implícita %", 10, 120, 25) / 100
        gr = calculate_full_greeks(p_mkt, k_s, 45/365, 0.045, vol_o)
        go1, go2, go3, go4, go5 = st.columns(5)
        go1.metric("Precio Call", f"${gr['price']:.2f}"); go2.metric("Delta Δ", f"{gr['delta']:.3f}")
        go3.metric("Gamma γ", f"{gr['gamma']:.4f}"); go4.metric("Vega ν", f"{gr['vega']:.3f}"); go5.metric("Theta θ", f"{gr['theta']:.2f}")

    with tabs[6]: # METODOLOGÍA
        st.header("Metodología Institucional")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)"); st.latex(r"TV = \frac{FCF_{10}(1+g)}{WACC-g}")
        
    with tabs[7]: # EXPORTAR
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income'); data['bs'].to_excel(wr, sheet_name='Balance'); data['cf'].to_excel(wr, sheet_name='CashFlow')
        st.download_button("💾 Descargar Master Excel", buf.getvalue(), f"COST_Model_{datetime.date.today()}.xlsx")

if __name__ == "__main__": main()
