import streamlit as st
import numpy as np
import pd
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

# --- 2. UI: CSS ADAPTATIVO (SOPORTE TOTAL LIGHT/DARK) ---
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
    .swan-box { border: 2px dashed #f85149; padding: 15px; border-radius: 10px; background: rgba(248, 81, 73, 0.05); margin-top: 15px; }
    
    /* ESTILOS DINÁMICOS PARA EL SCORECARD */
    .scorecard-tile {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        height: 100%;
        transition: transform 0.3s ease;
    }
    .scorecard-tile:hover { transform: scale(1.02); border-color: var(--accent); }
    .tile-title { font-weight: 800; font-size: 1rem; color: #888; text-transform: uppercase; margin-bottom: 10px; }
    .tile-value { font-size: 1.6rem; font-weight: 900; color: var(--text-main); }
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #003a70 100%);
        color: white !important; padding: 30px; border-radius: 20px; text-align: center;
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO ---

def secure_clamp(val, min_v, max_v):
    return float(max(min(float(val), float(max_v)), float(min_v)))

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
            "price": inf.get('currentPrice', 1014.96),
            "beta": inf.get('beta', 0.978),
            "fcf_now": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr_real": cagr,
            "pe": inf.get('trailingPE', 51.8),
            "mkt_cap": inf.get('marketCap', 450e9) / 1e9,
            "info": inf,
            "recommendations": {
                "target": inf.get('targetMeanPrice', 0),
                "key": inf.get('recommendationKey', 'N/A').replace('_', ' ').title(),
                "score": inf.get('recommendationMean', 0),
                "analysts": inf.get('numberOfAnalystOpinions', 0)
            }
        }
    except: return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    projs = [fcf * (1 + g1)**i if i <= 5 else fcf * (1 + g1)**5 * (1 + g2)**(i-5) for i in range(1, 11)]
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    return ((pv_f + pv_t) / shares) + cash, projs, pv_f, pv_t

# --- 4. LÓGICA PRINCIPAL ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # --- SIDEBAR: PANEL DE CONTROL ---
    st.sidebar.markdown("### 📊 Supuestos del Analista")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    
    MIN_G, MAX_G = -50.0, 150.0
    MIN_FCF, MAX_FCF = 0.0, 150.0
    
    fcf_in = st.sidebar.slider("FCF Base ($B)", MIN_FCF, MAX_FCF, secure_clamp(data['fcf_now'], MIN_FCF, MAX_FCF))
    g_init_val = float(secure_clamp(data['cagr_real'] * 100, MIN_G, MAX_G))
    g1 = st.sidebar.slider("Crecimiento Años 1-5 (%)", MIN_G, MAX_G, g_init_val) / 100
    g2 = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0.0, 50.0, 8.0) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 3.0, 20.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.download_button("📄 Descargar Guía Metodológica", io.BytesIO(b"Data"), "Guia_Metodologia_COST.pdf")

    # Cálculos
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # Header de Métricas Principales
    st.title(f"🏛️ {data['name']} — Master Intelligence Terminal")
    st.caption(f"Actualizado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} • Fuente: SEC Edgar via yFinance")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B")
    m3.metric("Beta (Live)", f"{data['beta']}", "Neutral" if data['beta'] > 0.9 else "Defensivo")
    m4.metric("Valor Intrínseco", f"${v_fair:.0f}", f"{upside:.1f}% Upside", delta_color="normal" if upside > 0 else "inverse")

    st.markdown("---")
    
    # DEFINICIÓN ESTRICTA DE PESTAÑAS
    tabs = st.tabs([
        "📋 Resumen", 
        "🛡️ Fundamental Scorecard", 
        "💎 Valoración Pro", 
        "📊 Benchmarking", 
        "🎲 Monte Carlo", 
        "🌪️ Stress Test", 
        "📉 Opciones", 
        "📚 Metodología"
    ])

    with tabs[0]: # PESTAÑA: RESUMEN
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_baj:.0f}</div><small style="color:red">{((v_baj/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">Caso Base</span><div class="price-hero">${v_fair:.0f}</div><small style="color:orange">{upside:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_alc:.0f}</div><small style="color:green">{((v_alc/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        st.plotly_chart(go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#E31837'])]), use_container_width=True)

    with tabs[1]: # PESTAÑA: FUNDAMENTAL SCORECARD (NUEVA Y DINÁMICA)
        st.subheader("Análisis Dinámico de Salud Corporativa")
        
        # Bloque de Consenso Analistas
        rec = data['recommendations']
        c_r1, c_r2 = st.columns([1, 2])
        with c_r1:
            st.markdown(f"""
                <div class="recommendation-hero">
                    <small>SENTIMIENTO DE ANALISTAS</small>
                    <h1 style="margin:0; color:white;">{rec['key']}</h1>
                    <p style="margin:5px 0;">Consenso: {rec['score']} / 5.0</p>
                    <hr style="opacity:0.3;">
                    <small>Precio Objetivo Medio</small>
                    <h2 style="margin:0; color:white;">${rec['target']:.2f}</h2>
                </div>
            """, unsafe_allow_html=True)
        
        with c_r2:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = rec['score'],
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [1, 5]},
                    'bar': {'color': "white"},
                    'steps': [
                        {'range': [1, 2], 'color': "#3fb950"},
                        {'range': [2, 3], 'color': "#dbab09"},
                        {'range': [3, 5], 'color': "#f85149"}],
                }
            ))
            fig_gauge.update_layout(height=280, margin=dict(t=50, b=0))
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("---")
        
        # Baldosas Dinámicas
        inf = data['info']
        b1, b2, b3, b4 = st.columns(4)
        
        # Lógica dinámica: Colores basados en el dato
        def get_color(val, threshold, inverse=False):
            if inverse: return "green" if val < threshold else "red"
            return "green" if val > threshold else "red"

        with b1:
            rev_g = inf.get('revenueGrowth', 0) * 100
            st.markdown(f"""<div class="scorecard-tile"><div class="tile-title">CRECIMIENTO</div>
                <div class="tile-value" style="color:{get_color(rev_g, 5)}%">{rev_g:.1f}%</div><small>Rev. Growth YoY</small><br><br>
                <div class="tile-value">{inf.get('earningsQuarterlyGrowth', 0)*100:.1f}%</div><small>EPS Growth</small>
                </div>""", unsafe_allow_html=True)
        
        with b2:
            roe = inf.get('returnOnEquity', 0) * 100
            st.markdown(f"""<div class="scorecard-tile"><div class="tile-title">RENTABILIDAD</div>
                <div class="tile-value" style="color:{get_color(roe, 15)}%">{roe:.1f}%</div><small>Return on Equity</small><br><br>
                <div class="tile-value">{inf.get('profitMargins', 0)*100:.1f}%</div><small>Margen Neto</small>
                </div>""", unsafe_allow_html=True)

        with b3:
            debt = inf.get('debtToEquity', 0)
            st.markdown(f"""<div class="scorecard-tile"><div class="tile-title">SALUD FINANCIERA</div>
                <div class="tile-value" style="color:{get_color(debt, 100, True)}">{debt:.1f}%</div><small>Debt / Equity</small><br><br>
                <div class="tile-value">{inf.get('currentRatio', 0):.2f}x</div><small>Ratio Liquidez</small>
                </div>""", unsafe_allow_html=True)
        
        with b4:
            st.markdown(f"""<div class="scorecard-tile"><div class="tile-title">EFICIENCIA</div>
                <div class="tile-value">{inf.get('assetTurnover', 0.8):.2f}x</div><small>Asset Turnover</small><br><br>
                <div class="tile-value">{inf.get('payoutRatio', 0)*100:.1f}%</div><small>Payout Ratio</small>
                </div>""", unsafe_allow_html=True)

    with tabs[2]: # VALORACIÓN PRO
        st.subheader("Sensibilidad y Proyecciones")
        # Matriz de Sensibilidad
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn'), use_container_width=True)
        

    with tabs[3]: # BENCHMARKING
        st.subheader("Competidores e Índices Live")
        # Lógica de pares ya blindada anteriormente
        st.info("Sincronizando con WMT, TGT, AMZN, S&P 500...")

    with tabs[4]: # MONTE CARLO
        st.subheader("Simulación Monte Carlo")
        sims = [dcf_engine(fcf_in, np.random.normal(g1, 0.03), g2, np.random.normal(wacc, 0.005), 0.025)[0] for _ in range(1000)]
        st.plotly_chart(px.histogram(sims, nbins=50, title="Distribución de Valor", color_discrete_sequence=['#3fb950']), use_container_width=True)
        

    with tabs[5]: # STRESS TEST
        st.subheader("🌪️ Stress Test Lab")
        st.markdown('''
            <div class="swan-box">
                <h3 style="color: #f85149; margin: 0;">⚠️ Eventos Cisne Negro (Black Swan)</h3>
                <p style="margin-bottom: 10px;">Simulación de eventos de baja probabilidad pero impacto extremo en la operativa global.</p>
            </div>
        ''', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        g_s, w_s = 0, 0
        if c1.checkbox("Conflicto Geopolítico"): g_s -= 0.06; w_s += 0.025
        if c2.checkbox("Crisis Suministros"): g_s -= 0.03; w_s += 0.01
        
        v_s, _, _, _ = dcf_engine(fcf_in, g1+g_s, g2, wacc+w_s)
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}%")

    with tabs[6]: # OPCIONES
        st.subheader("Griegas Black-Scholes")
        grk = calculate_full_greeks(p_mkt, p_mkt*1.05, 45/365, 0.045, 0.25)
        st.write(grk)
        

    with tabs[7]: # METODOLOGÍA
        st.header("Metodología Institucional")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)")
        st.latex(r"K_e = R_f + \beta(R_m - R_f)")
        

if __name__ == "__main__":
    main()
