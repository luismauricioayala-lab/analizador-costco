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

# --- 2. UI: CSS ADAPTATIVO INTEGRAL (EXPANDIDO) ---
st.markdown("""
    <style>
    :root {
        --text-main: var(--text-color);
        --bg-card: var(--secondary-background-color);
        --accent: #005BAA;
        --border: var(--border-color);
        --success: #3fb950;
        --warning: #f85149;
        --neutral: #888888;
    }
    
    /* Contenedores Principales */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        padding: 22px !important;
        border-radius: 12px !important;
    }
    
    /* Conclusiones de IA */
    .ai-concl-item {
        display: flex;
        align-items: center;
        margin-bottom: 12px;
        font-size: 1.05rem;
    }
    .ai-icon {
        margin-right: 12px;
        font-size: 1.2rem;
    }
    .ai-check { color: var(--success); }
    .ai-alert { color: #f97316; }
    
    /* Scorecard Tiles */
    .scorecard-tile {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        height: 100%;
    }
    .tile-title { font-weight: 800; font-size: 0.85rem; color: #888; text-transform: uppercase; margin-bottom: 10px; }
    .tile-value { font-size: 1.7rem; font-weight: 900; color: var(--text-main); }
    
    /* Recommendation Hero */
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #002d58 100%);
        color: white !important;
        padding: 35px; border-radius: 20px; text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    /* Cisne Negro */
    .swan-box {
        border: 2px dashed #f85149;
        padding: 25px;
        border-radius: 15px;
        background: rgba(248, 81, 73, 0.05);
        margin: 20px 0;
    }
    
    /* Escenarios */
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 15px; padding: 25px; text-align: center;
    }
    .price-hero { font-size: 42px; font-weight: 900; letter-spacing: -1.5px; margin: 10px 0; }
    .badge { padding: 5px 14px; border-radius: 20px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; }
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.1); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.1); border-color: #f85149; }
    .neutral-badge { color: #dbab09; background: rgba(219, 171, 9, 0.1); border-color: #dbab09; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO Y NORMALIZACIÓN ---

def secure_clamp(val, min_v, max_v):
    return float(max(min(float(val), float(max_v)), float(min_v)))

def normalize_radar_score(val, min_val, max_val, reverse=False):
    """Mapea un ratio a una escala de 1 a 6 para el gráfico de radar."""
    score = ((val - min_val) / (max_val - min_val)) * 5 + 1
    if reverse: score = 7 - score
    return secure_clamp(score, 1, 6)

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
            "is": asset.financials, "bs": asset.balance_sheet, "cf": cf_raw, "info": inf,
            "recommendations": {
                "target": inf.get('targetMeanPrice', 0),
                "key": inf.get('recommendationKey', 'N/A').replace('_', ' ').title(),
                "score": inf.get('recommendationMean', 0),
                "analysts": inf.get('numberOfAnalystOpinions', 0)
            }
        }
    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        return None

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
    price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2) if type=='call' else K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
    delta = norm.cdf(d1) if type=='call' else norm.cdf(d1) - 1
    return {"price": price, "delta": delta, "gamma": norm.pdf(d1)/(S*sigma*np.sqrt(T)), "vega": (S*np.sqrt(T)*norm.pdf(d1))/100, "theta": (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T))) - r*K*np.exp(-r*T)*norm.cdf(d1))/365}

# --- 4. LÓGICA PRINCIPAL ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # --- SIDEBAR ---
    st.sidebar.markdown("### 📊 Panel de Control")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 150.0, secure_clamp(data['fcf_now'], 0.0, 150.0))
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", -30.0, 150.0, float(secure_clamp(data['cagr_real']*100, -30.0, 150.0))) / 100
    wacc = st.sidebar.slider("WACC (%)", 3.0, 20.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.download_button("📄 Guía Metodológica", io.BytesIO(b"Data"), "COST_Methodology.pdf")

    # Cálculos
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, 0.08, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # --- HEADER CON BETA DINÁMICA ---
    st.title(f"🏛️ {data['name']} — Institutional Master")
    
    # Lógica de Beta Neutra
    b_val = data['beta']
    if 0.90 <= b_val <= 1.10:
        b_label, b_delta, b_color = "Riesgo Neutro", "±0.00", "off"
    elif b_val < 0.90:
        b_label, b_delta, b_color = "Baja Volatilidad", f"-{1.0-b_val:.2f}", "normal"
    else:
        b_label, b_delta, b_color = "Riesgo Agresivo", f"+{b_val-1.0:.2f}", "inverse"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B", "COST-NASDAQ")
    m3.metric("Riesgo Beta", f"{b_val:.3f}", b_label, delta_color=b_color)
    m4.metric("Valor Intrínseco", f"${v_fair:.0f}", f"{upside:.1f}% Upside", delta_color="normal" if upside > 0 else "inverse")

    st.markdown("---")
    
    # PESTAÑAS (Consolidadas y Completas)
    tabs = st.tabs([
        "📋 Resumen", "🛡️ Scorecard IA", "📊 Finanzas Pro", "💎 Valoración", 
        "📈 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones Lab", "📚 Metodología"
    ])

    with tabs[0]: # SUMMARY
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, 0.04, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, 0.10, wacc-0.01)
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_baj:.0f}</div><small style="color:#f85149">{((v_baj/p_mkt)-1)*100:.1f}%</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral-badge">Base Case</span><div class="price-hero">${v_fair:.0f}</div><small style="color:#dbab09">{upside:.1f}%</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_alc:.0f}</div><small style="color:#3fb950">{((v_alc/p_mkt)-1)*100:.1f}%</small></div>', unsafe_allow_html=True)
        st.plotly_chart(go.Figure(data=[go.Pie(labels=['Caja 10Y', 'Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA','#E31837'])]), use_container_width=True)

    with tabs[1]: # SCORECARD IA (NUEVO DISEÑO CON RADAR Y CONCLUSIONES)
        st.subheader("Conclusiones de IA y Perfil de Inversión")
        inf = data['info']
        
        c_diag1, c_diag2 = st.columns([1.2, 1])
        
        with c_diag1:
            # Lista de Conclusiones (Lógica de Diagnóstico)
            st.markdown("### 🔍 Diagnóstico del Analista")
            
            concl = [
                ("Analistas calificados como Compra", data['recommendations']['score'] < 2.5),
                ("Múltiplo P/E por encima del promedio del sector (Premium)", data['pe'] > 35),
                ("Margen ROE robusto (>20%)", inf.get('returnOnEquity',0) > 0.20),
                ("Los ingresos aumentaron YoY", inf.get('revenueGrowth',0) > 0),
                ("Deuda bajo control (Ratio < 1.0)", inf.get('currentRatio',0) > 1.0),
                ("Se prevé crecimiento positivo del BPA", inf.get('earningsQuarterlyGrowth',0) > 0)
            ]
            
            for text, condition in concl:
                icon = "🟢" if condition else "🟠"
                st.markdown(f'<div class="ai-concl-item"><span class="ai-icon">{icon}</span>{text}</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            # Recommendation Box
            rec = data['recommendations']
            st.markdown(f'<div class="recommendation-hero"><small>CONSENSO</small><h1>{rec["key"]}</h1><div>Score: {rec["score"]}/5.0</div><small>Target: ${rec["target"]:.2f}</small></div>', unsafe_allow_html=True)

        with c_diag2:
            # Gráfico de Radar
            radar_data = pd.DataFrame(dict(
                r=[
                    normalize_radar_score(data['pe'], 15, 60, True), # Valoración
                    normalize_radar_score(inf.get('profitMargins',0)*100, 1, 5), # Ganancias
                    normalize_radar_score(inf.get('revenueGrowth',0)*100, 0, 15), # Crecimiento
                    normalize_radar_score(inf.get('returnOnEquity',0)*100, 10, 30), # Rendimiento
                    normalize_radar_score(inf.get('currentRatio',0), 0.5, 2.0) # Estado
                ],
                theta=['Valoración', 'Ganancias', 'Crecimiento', 'Rendimiento', 'Estado']
            ))
            
            fig_radar = px.line_polar(radar_data, r='r', theta='theta', line_close=True, range_r=[1,6])
            fig_radar.update_traces(fill='toself', line_color='#005BAA', opacity=0.6)
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, showticklabels=False)), showlegend=False, height=450)
            st.plotly_chart(fig_radar, use_container_width=True)

    with tabs[2]: # FINANZAS PRO
        st.subheader("Análisis Dinámico de Estados Financieros")
        is_df, bs_df = data['is'], data['bs']
        try:
            ratios_yoy = pd.DataFrame({
                "Margen Bruto (%)": (is_df.loc['Gross Profit'] / is_df.loc['Total Revenue']) * 100,
                "Margen Neto (%)": (is_df.loc['Net Income'] / is_df.loc['Total Revenue']) * 100,
                "ROE (%)": (is_df.loc['Net Income'] / bs_df.loc['Stockholders Equity']) * 100
            }).T
            st.dataframe(ratios_yoy.style.format("{:.2f}"))
            c_f1, c_f2 = st.columns(2)
            c_f1.plotly_chart(px.line(is_df.loc[['Total Revenue', 'Net Income']].T, title="Ventas vs Utilidad"), use_container_width=True)
            c_f2.plotly_chart(px.bar(ratios_yoy.iloc[:2].T, barmode='group', title="Estructura de Márgenes"), use_container_width=True)
        except: st.warning("Datos financieros insuficientes para el análisis de tendencias.")

    with tabs[3]: # VALORACIÓN
        st.subheader("Sensibilidad y Trayectoria de Caja")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        fig_b = go.Figure()
        fig_b.add_trace(go.Scatter(x=h_x, y=data['fcf_hist'].values[::-1], name="Real", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_b.add_trace(go.Scatter(x=[h_x[-1]]+[str(int(h_x[-1])+i) for i in range(1,11)], y=[data['fcf_hist'].values[0]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash')))
        st.plotly_chart(fig_b, use_container_width=True)
        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, 0.08, w, g)[0] for g in gr] for w in wr]
        st.plotly_chart(px.imshow(pd.DataFrame(mtx, index=wr*100, columns=gr*100), text_auto='.0f', color_continuous_scale='RdYlGn', title="WACC vs G Perpetuo"), use_container_width=True)

    with tabs[4]: # BENCHMARKING
        st.subheader("Competidores e Índices en Tiempo Real")
        @st.cache_data(ttl=3600)
        def get_p(ts):
            rs = []
            for t in ts:
                try:
                    o = yf.Ticker(t); i = o.info
                    rs.append({'Ticker': i.get('symbol', t), 'PE': i.get('trailingPE', 25), 'Growth': i.get('revenueGrowth', 0.08)*100})
                except: continue
            return pd.DataFrame(rs)
        df_p = get_p(['COST', 'WMT', 'TGT', 'BJ', 'AMZN', '^GSPC', '^IXIC'])
        bc1, bc2 = st.columns(2)
        pal = px.colors.qualitative.Prism
        bc1.plotly_chart(px.bar(df_p, x='Ticker', y='PE', color='Ticker', title="P/E Live", color_discrete_sequence=pal), use_container_width=True)
        bc2.plotly_chart(px.scatter(df_p, x='Growth', y='PE', color='Ticker', text='Ticker', size='PE', title="Valuación vs Crecimiento", color_discrete_sequence=pal), use_container_width=True)

    with tabs[5]: # MONTE CARLO
        st.subheader("Simulación de Riesgo Estocástico (1,000 Iteraciones)")
        v_mc = st.slider("Volatilidad del Modelo (%)", 1, 10, 3) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1, v_mc), 0.08, np.random.normal(wacc, 0.005))[0] for _ in range(1000)]
        fig_mc = px.histogram(sims, nbins=50, title=f"Probabilidad de Upside: {(np.array(sims) > p_mkt).mean()*100:.1f}%", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="red", line_dash="dash", annotation_text="SPOT")
        st.plotly_chart(fig_mc, use_container_width=True)

    with tabs[6]: # STRESS TEST (FULL MACRO LAB + BLACK SWAN)
        st.subheader("🌪️ Laboratorio de Stress Macroeconómico")
        scol1, scol2 = st.columns(2)
        with scol1:
            sh_r = st.slider("Shock Ingresos (%)", -30, 10, 0)
            sh_u = st.slider("Alza Desempleo (%)", 3, 15, 4)
        with scol2:
            sh_i = st.slider("Inflación CPI (%)", 0, 15, 3)
            sh_w = st.slider("Alza Salarial (%)", 0, 12, 4)
        
        st.markdown('''<div class="swan-box"><h3 style="color: #f85149; margin: 0;">⚠️ Cisnes Negros (Black Swan)</h3>
            <p style="color: var(--text-main); margin-top: 5px; opacity: 0.8;">Simulación de eventos extremos sistémicos.</p></div>''', unsafe_allow_html=True)
        cw1, cw2, cw3 = st.columns(3)
        g_sw, w_sw = 0.0, 0.0
        if cw1.checkbox("Guerra Geopolítica"): g_sw -= 0.06; w_sw += 0.025
        if cw2.checkbox("Crisis Suministros"): g_sw -= 0.03; w_sw += 0.01
        if cw3.checkbox("Ciberataque"): g_sw -= 0.04; w_sw += 0.015
        
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(sh_r/100)-(sh_u/500)+g_sw, 0.08, wacc+(sh_i/500)+(sh_w/1000)+w_sw)
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs Base")

    with tabs[7]: # OPCIONES
        st.subheader("Griegas Black-Scholes")
        gr = calculate_full_greeks(p_mkt, p_mkt*1.05, 45/365, 0.045, 0.25)
        st.write(gr)

    with tabs[8]: # METODOLOGÍA
        st.header("Metodología Institucional")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)"); st.latex(r"K_e = R_f + \beta(R_m - R_f)")

if __name__ == "__main__":
    main()
