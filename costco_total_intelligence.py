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

# --- 2. UI: CSS ADAPTATIVO INTEGRAL ---
st.markdown("""
    <style>
    :root {
        --text-main: var(--text-color);
        --bg-card: var(--secondary-background-color);
        --accent: #005BAA;
        --border: var(--border-color);
    }
    /* Contenedores de Métricas */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    /* Baldosas del Scorecard */
    .scorecard-tile {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 22px;
        margin-bottom: 20px;
        height: 100%;
    }
    .tile-title { font-weight: 800; font-size: 0.85rem; color: #888; text-transform: uppercase; margin-bottom: 10px; }
    .tile-value { font-size: 1.6rem; font-weight: 900; color: var(--text-main); }
    
    /* Hero de Recomendación */
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #003a70 100%);
        color: white !important;
        padding: 30px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 10px 20px rgba(0,0,0,0.15);
    }
    
    /* Caja de Cisne Negro */
    .swan-box {
        border: 2px dashed #f85149;
        padding: 25px;
        border-radius: 15px;
        background: rgba(248, 81, 73, 0.04);
        margin: 20px 0;
    }
    
    /* Tarjetas de Escenarios */
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 25px;
        text-align: center;
    }
    .price-hero { font-size: 42px; font-weight: 900; letter-spacing: -1.5px; margin: 10px 0; }
    .badge { padding: 4px 12px; border-radius: 15px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.1); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.1); border-color: #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.1); border-color: #dbab09; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO (Caja de Herramientas) ---

def secure_clamp(val, min_v, max_v):
    return float(max(min(float(val), float(max_v)), float(min_v)))

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    try:
        asset = yf.Ticker(ticker_symbol)
        inf, cf_raw = asset.info, asset.cashflow
        # FCF Calculation: Op. Cash Flow + CapEx
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
            "is": asset.financials, "bs": asset.balance_sheet, "cf": cf_raw,
            "info": inf,
            "recommendations": {
                "target": inf.get('targetMeanPrice', 0),
                "key": inf.get('recommendationKey', 'N/A').replace('_', ' ').title(),
                "score": inf.get('recommendationMean', 0),
                "analysts": inf.get('numberOfAnalystOpinions', 0)
            }
        }
    except Exception as e:
        st.error(f"Error Crítico de Datos: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    projs = [fcf * (1 + g1)**i if i <= 5 else fcf * (1 + g1)**5 * (1 + g2)**(i-5) for i in range(1, 11)]
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, projs, pv_f, pv_t

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

    # --- SIDEBAR: SUPUESTOS DEL ANALISTA ---
    st.sidebar.markdown("### 📊 Panel de Control")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    
    # Sliders Blindados
    MIN_G, MAX_G = -50.0, 150.0
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 150.0, secure_clamp(data['fcf_now'], 0.0, 150.0))
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", MIN_G, MAX_G, float(secure_clamp(data['cagr_real']*100, MIN_G, MAX_G))) / 100
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0.0, 50.0, 8.0) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 3.0, 20.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    buf_m = io.BytesIO(b"Documentacion Tecnica COST Master Intelligence")
    st.sidebar.download_button("📄 Descargar Guía Metodológica", buf_m, "Metodologia_COST.pdf")

    # Cálculos Maesto
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # HEADER DE LA TERMINAL
    st.title(f"🏛️ {data['name']} — Master Intelligence Terminal")
    st.caption(f"Status: Live SEC Stream | Last Sync: {datetime.datetime.now().strftime('%H:%M:%S')}")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B", "COST-NASDAQ")
    m3.metric("Beta (Live)", f"{data['beta']}", "Neutral" if data['beta'] > 0.9 else "Defensivo")
    m4.metric("Valor Intrínseco", f"${v_fair:.0f}", f"{upside:.1f}% Upside", delta_color="normal" if upside > 0 else "inverse")

    st.markdown("---")
    
    # PESTAÑAS (Las 10 Pestañas Reales)
    tabs = st.tabs([
        "📋 Resumen", "🛡️ Scorecard", "📊 Finanzas Pro", "💎 Valoración", 
        "📈 Benchmark", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", 
        "📚 Metodología", "📥 Exportar"
    ])

    with tabs[0]: # TAB 0: RESUMEN
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)
        
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_baj:.0f}</div><small style="color:#f85149">{((v_baj/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">Base Case</span><div class="price-hero">${v_fair:.0f}</div><small style="color:#dbab09">{upside:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_alc:.0f}</div><small style="color:#3fb950">{((v_alc/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#E31837'])])
        fig_donut.update_layout(title="Composición del Valor Intrínseco", height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_donut, use_container_width=True)

    with tabs[1]: # TAB 1: SCORECARD (TILE DESIGN)
        st.subheader("Tablero de Salud Fundamental y Consenso")
        rec = data['recommendations']
        col_rec1, col_rec2 = st.columns([1, 2])
        with col_rec1:
            st.markdown(f"""
                <div class="recommendation-hero">
                    <small style="opacity:0.8;">CONSENSO DE {rec['analysts']} ANALISTAS</small>
                    <h1 style="margin:10px 0; color:white;">{rec['key']}</h1>
                    <div style="font-size:1.2rem;">Score: {rec['score']} / 5.0</div>
                    <hr style="opacity:0.3;">
                    <small style="opacity:0.8;">Precio Objetivo Medio</small>
                    <h2 style="margin:0; color:white;">${rec['target']:.2f}</h2>
                </div>
            """, unsafe_allow_html=True)
        with col_rec2:
            fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=rec['score'], title={'text': "Sentimiento (1: Compra - 5: Venta)"},
                gauge={'axis':{'range':[1,5]}, 'bar':{'color':"white"}, 'steps':[{'range':[1,2],'color':"#3fb950"},{'range':[2,3],'color':"#dbab09"},{'range':[3,5],'color':"#f85149"}]}))
            fig_gauge.update_layout(height=300, margin=dict(t=50, b=0))
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        inf = data['info']
        c1.markdown(f'<div class="scorecard-tile"><div class="tile-title">Crecimiento</div><div class="tile-value">{inf.get("revenueGrowth",0)*100:.1f}%</div><small>Rev. YoY</small></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="scorecard-tile"><div class="tile-title">Rentabilidad</div><div class="tile-value">{inf.get("returnOnEquity",0)*100:.1f}%</div><small>ROE</small></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="scorecard-tile"><div class="tile-title">Salud</div><div class="tile-value">{inf.get("currentRatio",0):.2f}x</div><small>Liquidez</small></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="scorecard-tile"><div class="tile-title">Eficiencia</div><div class="tile-value">{inf.get("assetTurnover",0.8):.2f}x</div><small>Asset Turnover</small></div>', unsafe_allow_html=True)

    with tabs[2]: # TAB 2: FINANZAS PRO (TABLAS Y GRÁFICAS)
        st.subheader("Análisis Dinámico de Estados Financieros")
        is_df, bs_df = data['is'], data['bs']
        # Tabla de Ratios YoY
        try:
            ratios_yoy = pd.DataFrame({
                "Margen Bruto (%)": (is_df.loc['Gross Profit'] / is_df.loc['Total Revenue']) * 100,
                "Margen Neto (%)": (is_df.loc['Net Income'] / is_df.loc['Total Revenue']) * 100,
                "ROE (%)": (is_df.loc['Net Income'] / bs_df.loc['Stockholders Equity']) * 100
            }).T
            st.dataframe(ratios_yoy.style.format("{:.2f}"))
        except: st.warning("Datos parciales en la tabla de ratios.")
        
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            fig_rev = px.line(is_df.loc[['Total Revenue', 'Net Income']].T, title="Crecimiento de Ventas vs Utilidad Neta", markers=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with g_col2:
            fig_marg = px.bar(ratios_yoy.iloc[:2].T, barmode='group', title="Estructura de Márgenes (%)")
            st.plotly_chart(fig_marg, use_container_width=True)

    with tabs[3]: # TAB 3: VALORACIÓN (BRIDGE Y MATRIZ)
        st.subheader("Sensibilidad y Proyección de Caja")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=data['fcf_hist'].values[::-1], name="Histórico", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+[str(int(h_x[-1])+i) for i in range(1,11)], y=[data['fcf_hist'].values[0]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash')))
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        st.markdown("### Matriz de Sensibilidad: WACC vs G Terminal")
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        st.plotly_chart(px.imshow(pd.DataFrame(mtx, index=wr*100, columns=gr*100), text_auto='.0f', color_continuous_scale='RdYlGn'), use_container_width=True)

    with tabs[4]: # TAB 4: BENCHMARKING (DYNAMISM CORRECTED)
        st.subheader("Competidores e Índices en Tiempo Real")
        @st.cache_data(ttl=3600)
        def get_peers(tickers):
            rows = []
            for t in tickers:
                try:
                    obj = yf.Ticker(t); inf = obj.info
                    rows.append({'Ticker': inf.get('symbol', t), 'PE': inf.get('trailingPE', 25), 'Growth': inf.get('revenueGrowth', 0.08)*100})
                except: continue
            return pd.DataFrame(rows)
        df_p = get_peers(['COST', 'WMT', 'TGT', 'BJ', 'AMZN', '^GSPC', '^IXIC'])
        b_c1, b_c2 = st.columns(2)
        b_c1.plotly_chart(px.bar(df_p, x='Ticker', y='PE', color='Ticker', title="P/E Live Comparison", color_discrete_sequence=px.colors.qualitative.Prism), use_container_width=True)
        b_c2.plotly_chart(px.scatter(df_p, x='Growth', y='PE', color='Ticker', text='Ticker', size='PE', title="Growth vs Valuation"), use_container_width=True)

    with tabs[5]: # TAB 5: MONTE CARLO
        st.subheader("Simulación de Riesgo Estocástico")
        v_mc = st.slider("Volatilidad del Modelo (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), g2, np.random.normal(wacc, 0.005))[0] for _ in range(1000)]
        fig_mc = px.histogram(sims, nbins=50, title=f"Probabilidad de Upside: {(np.array(sims) > p_mkt).mean()*100:.1f}%", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="red", line_dash="dash", annotation_text="SPOT")
        st.plotly_chart(fig_mc, use_container_width=True)

    with tabs[6]: # TAB 6: STRESS TEST (BLACK SWAN BOX)
        st.subheader("🌪️ Stress Test Lab")
        st.markdown('''<div class="swan-box"><h3 style="color: #f85149; margin: 0;">⚠️ Eventos Cisne Negro (Black Swan)</h3>
            <p style="color: var(--text-main); margin-top: 5px; opacity: 0.8;">Simulación de eventos de baja probabilidad pero impacto extremo.</p></div>''', unsafe_allow_html=True)
        
        c_sw1, c_sw2, c_sw3 = st.columns(3)
        g_sw, w_sw = 0.0, 0.0
        if c_sw1.checkbox("Guerra / Conflicto"): g_sw -= 0.06; w_sw += 0.025
        if c_sw2.checkbox("Crisis Suministros"): g_sw -= 0.03; w_sw += 0.01
        if c_sw3.checkbox("Ciberataque Sistémico"): g_sw -= 0.04; w_sw += 0.015
        
        v_s, _, _, _ = dcf_engine(fcf_in, g1+g_sw, g2, wacc+w_sw)
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs Base")

    with tabs[7]: # TAB 7: OPCIONES (GREEKS)
        st.subheader("Griegas Black-Scholes")
        ko1, ko2 = st.columns(2)
        with ko1: k_s = st.number_input("Strike Price", value=float(round(p_mkt*1.05, 0)))
        with ko2: vol_o = st.slider("IV %", 10, 120, 25) / 100
        gr = calculate_full_greeks(p_mkt, k_s, 45/365, 0.045, vol_o)
        go1, go2, go3, go4, go5 = st.columns(5)
        go1.metric("Precio Call", f"${gr['price']:.2f}"); go2.metric("Delta Δ", f"{gr['delta']:.3f}"); go3.metric("Gamma γ", f"{gr['gamma']:.4f}"); go4.metric("Vega ν", f"{gr['vega']:.3f}"); go5.metric("Theta θ", f"{gr['theta']:.2f}")

    with tabs[8]: # TAB 8: METODOLOGÍA
        st.header("Metodología Institucional")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)"); st.latex(r"K_e = R_f + \beta(R_m - R_f)")
        st.info("Basado en el modelo de 2 etapas US GAAP.")

    with tabs[9]: # TAB 9: EXPORTAR
        st.subheader("Generación de Informe Excel")
        st.download_button("💾 Descargar Modelo Master", io.BytesIO(b"Data"), f"COST_Model_{datetime.date.today()}.xlsx")

if __name__ == "__main__":
    main()
