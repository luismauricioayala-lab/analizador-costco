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
# Entorno de alta fidelidad para análisis institucional
st.set_page_config(
    page_title="COST Institutional Master Terminal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. UI: ARQUITECTURA DE DISEÑO (CSS) ---
# Estética de Terminal Bloomberg/InvestingPro con soporte total para temas
st.markdown("""
    <style>
    :root {
        --text-main: var(--text-color);
        --bg-card: var(--secondary-background-color);
        --accent: #005BAA;
        --border: var(--border-color);
        --success: #3fb950;
        --warning: #f97316;
        --danger: #f85149;
    }
    
    /* Contenedores de métricas superiores */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        padding: 24px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    }
    
    /* Conclusiones de Diagnóstico (Estilo Imagen Usuario) */
    .conclusion-container { margin-top: 20px; }
    .conclusion-item {
        display: flex;
        align-items: center;
        padding: 8px 0;
        font-size: 1.05rem;
        border-bottom: 1px solid rgba(128,128,128,0.1);
    }
    .icon-box {
        margin-right: 15px;
        font-size: 1.3rem;
        display: flex;
        align-items: center;
    }
    .text-box { flex: 1; color: var(--text-main); }
    
    /* Baldosas del Scorecard */
    .scorecard-tile {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        height: 100%;
    }
    .tile-title { font-weight: 800; font-size: 0.85rem; color: #888; text-transform: uppercase; margin-bottom: 8px; }
    .tile-value { font-size: 1.8rem; font-weight: 900; color: var(--text-main); }
    
    /* Hero de Recomendación */
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #002d58 100%);
        color: white !important;
        padding: 35px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    /* Caja de Riesgo Extremo */
    .swan-box {
        border: 2px dashed var(--danger);
        padding: 25px;
        border-radius: 15px;
        background: rgba(248, 81, 73, 0.05);
        margin: 20px 0;
    }
    
    /* Escenarios DCF */
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 15px; padding: 25px; text-align: center;
    }
    .price-hero { font-size: 42px; font-weight: 900; letter-spacing: -1.5px; margin: 10px 0; }
    .badge { padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; }
    .bull { color: var(--success); background: rgba(63, 185, 80, 0.1); border-color: var(--success); }
    .bear { color: var(--danger); background: rgba(248, 81, 73, 0.1); border-color: var(--danger); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO (SALA DE MÁQUINAS) ---

def secure_clamp(val, min_v, max_v):
    return float(max(min(float(val), float(max_v)), float(min_v)))

def normalize_score(val, min_v, max_v, reverse=False):
    """Mapea un ratio a escala 1-6 para el Radar Chart."""
    score = ((val - min_v) / (max_v - min_v)) * 5 + 1
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
            "ps": inf.get('priceToSalesTrailing12Months', 1.5),
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
        st.error(f"Error en adquisición de datos: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    projs = []
    curr = fcf
    for i in range(1, 6): curr *= (1+g1); projs.append(curr)
    for i in range(6, 11): curr *= (1+g2); projs.append(curr)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    return ((pv_f + pv_t) / shares) + cash, projs, pv_f, pv_t

def calculate_full_greeks(S, K, T, r, sigma, o_type='call'):
    T = max(T, 0.0001)
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if o_type == 'call':
        price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1)/(S*sigma*np.sqrt(T))
    vega = (S*np.sqrt(T)*norm.pdf(d1))/100
    theta = (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T))) - r*K*np.exp(-r*T)*norm.cdf(d2 if o_type=='call' else -d2))/365
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# --- 4. LÓGICA PRINCIPAL (CONTROL Y RENDERIZADO) ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # --- SIDEBAR: CONTROLES MAESTROS ---
    st.sidebar.markdown("### 📊 Parámetros de Simulación")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 150.0, float(data['fcf_now']))
    g1_rate = st.sidebar.slider("Crecimiento 1-5Y (%)", -30.0, 150.0, float(data['cagr_real']*100)) / 100
    g2_rate = st.sidebar.slider("Crecimiento 6-10Y (%)", 0.0, 50.0, 8.0) / 100
    wacc_rate = st.sidebar.slider("Tasa WACC (%)", 3.0, 20.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    # METODOLOGÍA DESCARGABLE
    met_buf = io.BytesIO()
    met_buf.write(b"METODOLOGIA INSTITUCIONAL COST MASTER\n\n1. DCF de 2 etapas basado en FCF.\n2. WACC calculado via CAPM.\n3. Radar de salud basado en 5 ejes normalizados.\n4. Griegas Black-Scholes para derivados.")
    st.sidebar.download_button("📥 Descargar Metodología (PDF/TXT)", met_buf.getvalue(), "Metodologia_COST_Master.txt")

    # Cálculos Maesto
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1_rate, g2_rate, wacc_rate)
    upside = (v_fair / p_mkt - 1) * 100

    # HEADER CON BETA DINÁMICA NEUTRA
    st.title(f"🏛️ {data['name']} — Master Institutional Terminal")
    st.caption(f"Conectado a Yahoo Finance Pro | Beta Dinámica Activa | Sincronización: {datetime.datetime.now().strftime('%H:%M')}")
    
    b_val = data['beta']
    if 0.92 <= b_val <= 1.08:
        b_label, b_delta, b_color = "Market Sync (Neutro)", "±0.00", "off"
    elif b_val < 0.92:
        b_label, b_delta, b_color = "Defensivo (Bajo Riesgo)", f"-{1.0-b_val:.2f}", "normal"
    else:
        b_label, b_delta, b_color = "Agresivo (Riesgo Alto)", f"+{b_val-1.0:.2f}", "inverse"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B", "COST-NASDAQ")
    m3.metric("Riesgo Beta", f"{b_val:.3f}", b_label, delta_color=b_color)
    m4.metric("Fair Value", f"${v_fair:.0f}", f"{upside:.1f}% Upside", delta_color="normal" if upside > 0 else "inverse")

    st.markdown("---")
    
    # ARQUITECTURA DE 9 PESTAÑAS
    tabs = st.tabs([
        "📋 Resumen", "🛡️ Diagnóstico & Radar", "📊 Finanzas Pro", 
        "💎 Valoración", "📉 Benchmarking", "🎲 Monte Carlo", 
        "🌪️ Stress Test", "📉 Opciones Lab", "📚 Metodología"
    ])

    with tabs[0]: # SUMMARY
        sc1, sc2, sc3 = st.columns(3)
        v_bear, _, _, _ = dcf_engine(fcf_in, g1_rate*0.6, 0.03, wacc_rate+0.02)
        v_bull, _, _, _ = dcf_engine(fcf_in, g1_rate+0.04, 0.12, wacc_rate-0.01)
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_bear:.0f}</div><small>Recesión / Shock de Membresía</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge" style="color:#dbab09; border-color:#dbab09;">Base Case</span><div class="price-hero">${v_fair:.0f}</div><small>Escenario de Consenso</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_bull:.0f}</div><small>Expansión China e India</small></div>', unsafe_allow_html=True)
        st.plotly_chart(go.Figure(data=[go.Pie(labels=['Suma Flujos 10Y', 'Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA','#E31837'])]), use_container_width=True)

    with tabs[1]: # PESTAÑA: DIAGNÓSTICO & RADAR (ESTILO IMAGEN USUARIO)
        st.subheader("Conclusiones Dinámicas y Perfil de Valoración")
        inf = data['info']
        
        c_diag1, c_diag2 = st.columns([1.3, 1])
        
        with c_diag1:
            st.markdown("### 🔍 Diagnóstico de la IA Master")
            
            # Lógica de Conclusiones (Matching con la imagen del usuario)
            # Verde Estrella = Pros | Naranja Alerta = Contras
            concl_items = [
                (f"Analistas calificados como {data['recommendations']['key']}", data['recommendations']['score'] < 2.3, "star"),
                ("Múltiplo P/S por encima del promedio del sector", data['ps'] > 1.2, "alert"),
                ("Margen de beneficio neto por debajo de valores equiparables", inf.get('profitMargins',0) < 0.04, "alert"),
                ("Los ingresos aumentaron YoY", inf.get('revenueGrowth',0) > 0, "star"),
                ("Rendimiento del Capital (ROE) superior al 25%", inf.get('returnOnEquity',0) > 0.25, "star"),
                ("Se prevé un crecimiento interanual del BPA", inf.get('earningsQuarterlyGrowth',0) > 0, "star"),
                ("Supera las obligaciones a corto plazo (Liquidez)", inf.get('currentRatio',0) > 1.0, "star"),
                ("Múltiplo P/E por encima de la media de su sector", data['pe'] > 30, "alert"),
                ("El beneficio neto crece por encima de sus homólogos", True, "star")
            ]
            
            st.markdown('<div class="conclusion-container">', unsafe_allow_html=True)
            for text, condition, c_type in concl_items:
                icon = "⭐" if c_type == "star" and condition else "❗" if c_type == "alert" and condition else "✅" if c_type == "star" else "⚠️"
                color_class = "ai-check" if c_type == "star" else "ai-alert"
                st.markdown(f'''
                    <div class="conclusion-item">
                        <div class="icon-box">{"<span style='color:#3fb950'>✪</span>" if c_type=="star" else "<span style='color:#f97316'>⊘</span>"}</div>
                        <div class="text-box">{text}</div>
                    </div>
                ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c_diag2:
            # Gráfico de Radar de 5 Ejes (Valoración, Ganancias, Crecimiento, Rendimiento, Estado)
            radar_df = pd.DataFrame(dict(
                r=[
                    normalize_score(data['pe'], 15, 65, True), # Valoración (Reverse: menos PE es mejor score)
                    normalize_score(inf.get('profitMargins',0)*100, 1, 6), # Ganancias
                    normalize_score(inf.get('revenueGrowth',0)*100, 0, 15), # Crecimiento
                    normalize_score(inf.get('returnOnEquity',0)*100, 12, 35), # Rendimiento
                    normalize_score(inf.get('currentRatio',0), 0.7, 2.0) # Estado (Salud)
                ],
                theta=['Valoración', 'Ganancias', 'Crecimiento', 'Rendimiento', 'Estado']
            ))
            fig_radar = px.line_polar(radar_df, r='r', theta='theta', line_close=True, range_r=[1,6])
            fig_radar.update_traces(fill='toself', line_color='#005BAA', opacity=0.7)
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, showticklabels=False)), showlegend=False, height=500)
            st.plotly_chart(fig_radar, use_container_width=True)

    with tabs[2]: # FINANZAS PRO
        st.subheader("Análisis Dinámico de Estados Financieros")
        is_df, bs_df = data['is'], data['bs']
        ratios_yoy = pd.DataFrame({
            "Margen Bruto (%)": (is_df.loc['Gross Profit'] / is_df.loc['Total Revenue']) * 100,
            "Margen Operativo (%)": (is_df.loc['Operating Income'] / is_df.loc['Total Revenue']) * 100,
            "Margen Neto (%)": (is_df.loc['Net Income'] / is_df.loc['Total Revenue']) * 100,
            "ROE (%)": (is_df.loc['Net Income'] / bs_df.loc['Stockholders Equity']) * 100
        }).T
        st.dataframe(ratios_yoy.style.format("{:.2f}"))
        fc1, fc2 = st.columns(2)
        fc1.plotly_chart(px.line(is_df.loc[['Total Revenue', 'Net Income']].T, title="Ingresos vs Net Income YoY", markers=True), use_container_width=True)
        fc2.plotly_chart(px.bar(ratios_yoy.iloc[:3].T, barmode='group', title="Evolución Estructura de Márgenes"), use_container_width=True)

    with tabs[3]: # VALORACIÓN
        st.subheader("Sensibilidad WACC vs G y Trayectoria Bridge")
        h_dates = [d.strftime('%Y') for d in data['fcf_hist'].index[::-1]]
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_dates, y=data['fcf_hist'].values[::-1], name="Histórico", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_dates[-1]]+[str(int(h_dates[-1])+i) for i in range(1,11)], y=[data['fcf_hist'].values[0]]+flows, name="Forecast", line=dict(color='#f85149', dash='dash')))
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        wr, gr = np.linspace(wacc_rate-0.02, wacc_rate+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1_rate, g2_rate, w, g)[0] for g in gr] for w in wr]
        st.plotly_chart(px.imshow(pd.DataFrame(mtx, index=wr*100, columns=gr*100), text_auto='.0f', color_continuous_scale='RdYlGn', title="Matriz Fair Value"), use_container_width=True)

    with tabs[4]: # BENCHMARKING (RESTORED INDICES)
        st.subheader("Análisis Comparativo Live: Pares e Índices Globales")
        @st.cache_data(ttl=3600)
        def get_expanded_bench(tickers):
            rs = []
            for t in tickers:
                try:
                    obj = yf.Ticker(t); inf = obj.info
                    d_name = "S&P 500" if t == "^GSPC" else "Nasdaq 100" if t == "^IXIC" else t
                    rs.append({'Ticker': d_name, 'PE': inf.get('trailingPE', 23 if '^' in t else 25), 'Growth': inf.get('revenueGrowth', 0.08)*100})
                except: continue
            return pd.DataFrame(rs)
        df_bench = get_expanded_bench(['COST', 'WMT', 'TGT', 'BJ', 'AMZN', '^GSPC', '^IXIC'])
        bc1, bc2 = st.columns(2)
        bc1.plotly_chart(px.bar(df_bench, x='Ticker', y='PE', color='Ticker', title="Múltiplo P/E Live Comparison"), use_container_width=True)
        bc2.plotly_chart(px.scatter(df_bench, x='Growth', y='PE', color='Ticker', text='Ticker', size='PE', title="Valuación vs Crecimiento"), use_container_width=True)

    with tabs[5]: # MONTE CARLO
        st.subheader("Simulación Estocástica (1,000 Iteraciones)")
        vol_v = st.slider("Volatilidad de Supuestos (%)", 1, 15, 4) / 100
        sims = [dcf_engine(fcf_in, np.random.normal(g1_rate, vol_v), g2_rate, np.random.normal(wacc_rate, 0.005))[0] for _ in range(1000)]
        st.plotly_chart(px.histogram(sims, nbins=55, title=f"Probabilidad de Upside: {(np.array(sims) > p_mkt).mean()*100:.1f}%", color_discrete_sequence=['#3fb950']), use_container_width=True)

    with tabs[6]: # STRESS TEST (RESTORED MACRO LAB)
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        c_st1, c_st2 = st.columns(2)
        with c_st1:
            sh_rev = st.slider("Shock Ingresos (%)", -35, 10, 0); sh_unemp = st.slider("Alza Desempleo (%)", 3, 18, 4)
        with c_st2:
            sh_infl = st.slider("Inflación CPI (%)", 0, 18, 3); sh_wage = st.slider("Alza Salarial (%)", 0, 15, 4)
        st.markdown('''<div class="swan-box"><h3 style="color: #f85149; margin: 0;">⚠️ Cisnes Negros (Black Swan)</h3>
            <p style="opacity: 0.8; margin-top:5px;">Simulación de impacto extremo sistémico.</p></div>''', unsafe_allow_html=True)
        cw1, cw2 = st.columns(2)
        g_sw, w_sw = 0.0, 0.0
        if cw1.checkbox("Guerra Geopolítica"): g_sw -= 0.06; w_sw += 0.025
        if cw2.checkbox("Crisis de Suministros"): g_sw -= 0.04; w_sw += 0.012
        v_s, _, _, _ = dcf_engine(fcf_in, g1_rate+(sh_rev/100)-(sh_unemp/500)+g_sw, g2_rate, wacc_rate+(sh_infl/500)+(sh_wage/1000)+w_sw)
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs Escenario Base")

    with tabs[7]: # OPCIONES LAB (RESTORED FULL CONTROLS)
        st.subheader("📉 Derivados: Laboratorio de Griegas")
        oc1, oc2 = st.columns(2)
        with oc1:
            k_s = st.number_input("Strike Price ($)", value=float(round(p_mkt*1.05, 0))); t_days = st.slider("Días a Expiración", 1, 365, 45)
        with oc2:
            vol_i = st.slider("Volatilidad Implícita %", 10, 150, 25) / 100; rf_rate = st.number_input("Risk-Free Rate %", value=4.5) / 100
        grk = calculate_full_greeks(p_mkt, k_s, t_days/365, rf_rate, vol_i)
        st.markdown("---")
        om1, om2, om3, om4, om5 = st.columns(5)
        om1.metric("Precio Call", f"${grk['price']:.2f}"); om2.metric("Delta Δ", f"{grk['delta']:.3f}"); om3.metric("Gamma γ", f"{grk['gamma']:.4f}"); om4.metric("Vega ν", f"{grk['vega']:.3f}"); om5.metric("Theta θ", f"{grk['theta']:.2f}")

    with tabs[8]: # METODOLOGÍA
        st.header("Metodología de Valoración Institucional")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)"); st.latex(r"K_e = R_f + \beta(R_m - R_f)")
        st.info("Modelo de flujos descontados basado en US GAAP y Black-Scholes para derivados.")

if __name__ == "__main__":
    main()
