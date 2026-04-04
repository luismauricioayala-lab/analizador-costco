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
# Establecemos el entorno de trabajo profesional con layout expandido
st.set_page_config(
    page_title="COST Institutional Master",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. UI: ARQUITECTURA DE DISEÑO (CSS) ---
# Definimos el estilo Bloomberg/Institutional para baldosas, cajas de riesgo y métricas
st.markdown("""
    <style>
    :root {
        --text-main: var(--text-color);
        --bg-card: var(--secondary-background-color);
        --accent: #005BAA;
        --border: var(--border-color);
        --red-alert: #f85149;
        --green-bull: #3fb950;
    }
    
    /* Contenedor de métricas superiores */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        padding: 22px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Baldosas dinámicas del Scorecard */
    .scorecard-tile {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        height: 100%;
        transition: transform 0.2s;
    }
    .scorecard-tile:hover {
        border-color: var(--accent);
        transform: translateY(-2px);
    }
    .tile-title { font-weight: 800; font-size: 0.85rem; color: #888; text-transform: uppercase; margin-bottom: 8px; }
    .tile-value { font-size: 1.7rem; font-weight: 900; color: var(--text-main); }
    
    /* Hero de Recomendación de Analistas */
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #002d58 100%);
        color: white !important;
        padding: 35px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }
    
    /* Caja de Cisne Negro (Black Swan) */
    .swan-box {
        border: 2px dashed var(--red-alert);
        padding: 25px;
        border-radius: 15px;
        background: rgba(248, 81, 73, 0.04);
        margin: 20px 0;
    }
    
    /* Tarjetas de Escenarios DCF */
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 25px;
        text-align: center;
    }
    .price-hero { font-size: 42px; font-weight: 900; letter-spacing: -1.5px; margin: 10px 0; }
    .badge { padding: 5px 14px; border-radius: 20px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; }
    .bull { color: var(--green-bull); background: rgba(63, 185, 80, 0.1); border-color: var(--green-bull); }
    .bear { color: var(--red-alert); background: rgba(248, 81, 73, 0.1); border-color: var(--red-alert); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO (SALA DE MÁQUINAS) ---

def secure_clamp(val, min_v, max_v):
    """Garantiza estabilidad en los tipos de datos para Streamlit Sliders."""
    return float(max(min(float(val), float(max_v)), float(min_v)))

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    """Extracción masiva de datos: Info, Financials, Balance Sheet y Cashflow."""
    try:
        asset = yf.Ticker(ticker_symbol)
        inf = asset.info
        cf_raw = asset.cashflow
        # Calculamos FCF: Flujo operativo + Inversiones de capital (CapEx es negativo)
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        v_hist = fcf_series.values[::-1]
        # Cálculo de tasa de crecimiento histórica (CAGR)
        if len(v_hist) > 1 and v_hist[0] > 0:
            cagr = (v_hist[-1] / v_hist[0])**(1 / (len(v_hist) - 1)) - 1
        else:
            cagr = 0.12
            
        return {
            "name": inf.get('longName', 'Costco Wholesale'),
            "price": inf.get('currentPrice', 1014.96),
            "beta": inf.get('beta', 0.978),
            "fcf_now": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr_real": cagr,
            "pe": inf.get('trailingPE', 51.8),
            "mkt_cap": inf.get('marketCap', 450e9) / 1e9,
            "is": asset.financials,
            "bs": asset.balance_sheet,
            "cf": cf_raw,
            "info": inf,
            "recommendations": {
                "target": inf.get('targetMeanPrice', 0),
                "key": inf.get('recommendationKey', 'N/A').replace('_', ' ').title(),
                "score": inf.get('recommendationMean', 0),
                "analysts": inf.get('numberOfAnalystOpinions', 0)
            }
        }
    except Exception as e:
        st.error(f"Fallo Crítico en la Extracción de Datos: {e}")
        return None

def dcf_engine(fcf, g1, g2, wacc, gt=0.025, shares=0.4436, cash=22.0):
    """Motor de Valoración por Flujos Descontados (2 Etapas)."""
    # Etapa 1: Crecimiento Acelerado (Años 1-5)
    # Etapa 2: Crecimiento de Transición (Años 6-10)
    projs = []
    current_fcf = fcf
    for i in range(1, 6):
        current_fcf *= (1 + g1)
        projs.append(current_fcf)
    for i in range(6, 11):
        current_fcf *= (1 + g2)
        projs.append(current_fcf)
        
    # Descuento a Valor Presente
    pv_fcf = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    
    # Valor Terminal (G Perpetuo)
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_tv = tv / (1 + wacc)**10
    
    total_value = ((pv_fcf + pv_tv) / shares) + cash
    return total_value, projs, pv_fcf, pv_tv

def calculate_full_greeks(S, K, T, r, sigma, option_type='call'):
    """Motor Matemático Black-Scholes para Derivados."""
    T = max(T, 0.0001)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    theta = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d2 if option_type == 'call' else -d2)) / 365
    
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# --- 4. LÓGICA DE INTERFAZ (FRONT-END) ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # --- SIDEBAR: PANEL DE SUPUESTOS ---
    st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Costco_Wholesale_logo_2010-2015.svg/2560px-Costco_Wholesale_logo_2010-2015.svg.png", width=150)
    st.sidebar.markdown("### 📊 Supuestos del Modelo")
    
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']), step=1.0)
    
    st.sidebar.markdown("**Flujos de Caja**")
    fcf_base = st.sidebar.slider("FCF Base ($B)", 0.0, 150.0, float(data['fcf_now']))
    g1_rate = st.sidebar.slider("Crecimiento 1-5Y (%)", -30.0, 150.0, float(data['cagr_real'] * 100)) / 100
    g2_rate = st.sidebar.slider("Crecimiento 6-10Y (%)", 0.0, 50.0, 8.0) / 100
    
    st.sidebar.markdown("**Tasas de Descuento**")
    wacc_rate = st.sidebar.slider("Tasa WACC (%)", 3.0, 20.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    st.sidebar.info("Este modelo utiliza una metodología de 2 etapas con Valor Terminal basado en crecimiento perpetuo.")

    # Cálculos Maesto del Escenario Base
    v_intrinsic, flows_proj, pv_cash, pv_term = dcf_engine(fcf_base, g1_rate, g2_rate, wacc_rate)
    upside_pot = (v_intrinsic / p_mkt - 1) * 100

    # --- HEADER: MÉTRICAS EN TIEMPO REAL ---
    st.title(f"🏛️ {data['name']} Intelligence Terminal")
    st.caption(f"Sincronización SEC EDGAR: Live | Last Update: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Lógica de Beta Dinámica y Neutra
    beta_val = data['beta']
    if 0.92 <= beta_val <= 1.08:
        beta_label, beta_delta, beta_color = "Market Sync", "±0.00", "off"
    elif beta_val < 0.92:
        beta_label, beta_delta, beta_color = "Defensivo", f"-{1.0 - beta_val:.2f}", "normal"
    else:
        beta_label, beta_delta, beta_color = "Agresivo", f"+{beta_val - 1.0:.2f}", "inverse"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium Valuation")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B", "COST-NASDAQ")
    m3.metric("Riesgo Beta", f"{beta_val:.3f}", beta_label, delta_color=beta_color)
    m4.metric("Valor Intrínseco", f"${v_intrinsic:.0f}", f"{upside_pot:.1f}% Upside", delta_color="normal" if upside_pot > 0 else "inverse")

    st.markdown("---")
    
    # --- ARQUITECTURA DE PESTAÑAS (9 SECCIONES) ---
    tabs = st.tabs([
        "📋 Resumen", "🛡️ Scorecard Analista", "📊 Finanzas Pro", 
        "💎 Valoración", "📉 Benchmarking", "🎲 Monte Carlo", 
        "🌪️ Stress Test", "📉 Opciones Lab", "📚 Metodología"
    ])

    with tabs[0]: # PESTAÑA: RESUMEN
        st.subheader("Análisis de Escenarios y Composición del Valor")
        sc1, sc2, sc3 = st.columns(3)
        
        # Escenarios automáticos
        v_bear, _, _, _ = dcf_engine(fcf_base, g1_rate * 0.5, 0.03, wacc_rate + 0.02)
        v_bull, _, _, _ = dcf_engine(fcf_base, g1_rate + 0.03, 0.10, wacc_rate - 0.01)
        
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_bear:.0f}</div><small>Pesimismo Macroeconómico</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge" style="color:#dbab09; border-color:#dbab09;">Caso Base</span><div class="price-hero">${v_intrinsic:.0f}</div><small>Supuestos Actuales</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_bull:.0f}</div><small>Expansión Global Óptima</small></div>', unsafe_allow_html=True)
        
        st.plotly_chart(go.Figure(data=[go.Pie(labels=['Suma Flujos 10Y', 'Valor Terminal'], values=[pv_cash, pv_term], hole=.6, marker_colors=['#005BAA','#E31837'])]), use_container_width=True)

    with tabs[1]: # PESTAÑA: SCORECARD (BALDOSAS + GAUGE)
        st.subheader("Consenso de Mercado y Ratios de Calidad")
        rec = data['recommendations']
        col_r1, col_r2 = st.columns([1, 2])
        
        with col_r1:
            st.markdown(f"""
                <div class="recommendation-hero">
                    <small>CONSENSO DE {rec['analysts']} ANALISTAS</small>
                    <h1 style="margin:10px 0; color:white;">{rec['key']}</h1>
                    <div style="font-size:1.2rem;">Score: {rec['score']} / 5.0</div>
                    <hr style="opacity:0.3;">
                    <small>Precio Objetivo (Mean Target)</small>
                    <h2 style="margin:0; color:white;">${rec['target']:.2f}</h2>
                </div>
            """, unsafe_allow_html=True)
            
        with col_r2:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = rec['score'],
                title = {'text': "Sentimiento (1: Compra Fuerte - 5: Venta)"},
                gauge = {
                    'axis': {'range': [1, 5]},
                    'bar': {'color': "white"},
                    'steps': [
                        {'range': [1, 2], 'color': "#3fb950"},
                        {'range': [2, 3], 'color': "#dbab09"},
                        {'range': [3, 5], 'color': "#f85149"}]
                }
            ))
            fig_gauge.update_layout(height=350, margin=dict(t=50, b=0, l=30, r=30))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
        st.markdown("---")
        # Tiles de Ratios Fundamentales
        inf = data['info']
        b1, b2, b3, b4 = st.columns(4)
        b1.markdown(f'<div class="scorecard-tile"><div class="tile-title">Crecimiento</div><div class="tile-value">{inf.get("revenueGrowth",0)*100:.1f}%</div><small>Revenue Growth YoY</small></div>', unsafe_allow_html=True)
        b2.markdown(f'<div class="scorecard-tile"><div class="tile-title">Rentabilidad</div><div class="tile-value">{inf.get("returnOnEquity",0)*100:.1f}%</div><small>ROE TTM</small></div>', unsafe_allow_html=True)
        b3.markdown(f'<div class="scorecard-tile"><div class="tile-title">Salud Financiera</div><div class="tile-value">{inf.get("currentRatio",0):.2f}x</div><small>Current Ratio</small></div>', unsafe_allow_html=True)
        b4.markdown(f'<div class="scorecard-tile"><div class="tile-title">Eficiencia</div><div class="tile-value">{inf.get("assetTurnover",0.8):.2f}x</div><small>Asset Turnover</small></div>', unsafe_allow_html=True)

    with tabs[2]: # PESTAÑA: FINANZAS PRO (TABLAS Y TENDENCIAS)
        st.subheader("Estados Financieros y Evolución Histórica")
        is_st, bs_st = data['is'], data['bs']
        
        # Tabla de Ratios de los últimos años
        try:
            ratios_table = pd.DataFrame({
                "Margen Bruto (%)": (is_st.loc['Gross Profit'] / is_st.loc['Total Revenue']) * 100,
                "Margen Operativo (%)": (is_st.loc['Operating Income'] / is_st.loc['Total Revenue']) * 100,
                "Margen Neto (%)": (is_st.loc['Net Income'] / is_st.loc['Total Revenue']) * 100,
                "ROE (%)": (is_st.loc['Net Income'] / bs_st.loc['Stockholders Equity']) * 100
            }).T
            st.dataframe(ratios_table.style.format("{:.2f}"))
        except:
            st.warning("No se pudieron calcular todos los ratios debido a datos incompletos en la API.")
            
        st.markdown("---")
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            fig_trend = px.line(is_st.loc[['Total Revenue', 'Net Income']].T, title="Ingresos vs Utilidad Neta (Historico)", markers=True, template="plotly_white")
            fig_trend.update_layout(colorway=['#005BAA', '#E31837'])
            st.plotly_chart(fig_trend, use_container_width=True)
        with fcol2:
            fig_margin = px.bar(ratios_table.iloc[:3].T, barmode='group', title="Evolución de Márgenes (%)", template="plotly_white")
            st.plotly_chart(fig_margin, use_container_width=True)

    with tabs[3]: # PESTAÑA: VALORACIÓN (BRIDGE + SENSITIVITY)
        st.subheader("Análisis Detallado de Flujos y Sensibilidad")
        # Gráfico Bridge de Proyección
        h_dates = [d.strftime('%Y') for d in data['fcf_hist'].index[::-1]]
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_dates, y=data['fcf_hist'].values[::-1], name="Histórico", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_dates[-1]]+[str(int(h_dates[-1])+i) for i in range(1,11)], y=[data['fcf_hist'].values[0]]+flows_proj, name="Estimado (10Y)", line=dict(color='#f85149', dash='dash', width=4)))
        st.plotly_chart(fig_bridge, use_container_width=True)
        
        st.markdown("### Matriz de Sensibilidad: WACC vs G Perpetuo")
        w_range = np.linspace(wacc_rate-0.02, wacc_rate+0.02, 5)
        g_range = np.linspace(0.015, 0.035, 5)
        mtx_data = [[dcf_engine(fcf_base, g1_rate, g2_rate, w, g)[0] for g in g_range] for w in w_range]
        df_sens = pd.DataFrame(mtx_data, index=[f"{x*100:.1f}%" for x in w_range], columns=[f"{x*100:.1f}%" for x in g_range])
        st.plotly_chart(px.imshow(df_sens, text_auto='.0f', color_continuous_scale='RdYlGn', labels=dict(x="G Perpetuo", y="WACC", color="Fair Value")), use_container_width=True)

    with tabs[4]: # PESTAÑA: BENCHMARKING (INDICES RESTAURADOS)
        st.subheader("Análisis Comparativo Live: Pares e Índices")
        @st.cache_data(ttl=3600)
        def get_expanded_benchmark(ticker_list):
            results = []
            for t in ticker_list:
                try:
                    obj = yf.Ticker(t); inf_obj = obj.info
                    disp_name = "S&P 500" if t == "^GSPC" else "Nasdaq 100" if t == "^IXIC" else t
                    results.append({
                        'Ticker': disp_name, 
                        'PE': inf_obj.get('trailingPE', 22.5 if '^' in t else 25), 
                        'Growth': inf_obj.get('revenueGrowth', 0.08) * 100
                    })
                except: continue
            return pd.DataFrame(results)
            
        df_bench = get_expanded_benchmark(['COST', 'WMT', 'TGT', 'BJ', 'AMZN', '^GSPC', '^IXIC'])
        bc1, bc2 = st.columns(2)
        bc1.plotly_chart(px.bar(df_bench, x='Ticker', y='PE', color='Ticker', title="Múltiplo P/E Live", template="plotly_white"), use_container_width=True)
        bc2.plotly_chart(px.scatter(df_bench, x='Growth', y='PE', color='Ticker', text='Ticker', size='PE', title="Crecimiento vs Valuación"), use_container_width=True)

    with tabs[5]: # PESTAÑA: MONTE CARLO
        st.subheader("Simulación de Monte Carlo (1,000 Iteraciones)")
        vol_slider = st.slider("Incertidumbre en Crecimiento (SD %)", 1, 15, 4) / 100
        sim_results = []
        for _ in range(1000):
            g_rand = np.random.normal(g1_rate, vol_slider)
            w_rand = np.random.normal(wacc_rate, 0.006)
            sim_v, _, _, _ = dcf_engine(fcf_base, g_rand, g2_rate, w_rand)
            sim_results.append(sim_v)
            
        prob_upside = (np.array(sim_results) > p_mkt).mean() * 100
        fig_hist = px.histogram(sim_results, nbins=60, title=f"Probabilidad de Upside: {prob_upside:.1f}%", color_discrete_sequence=['#3fb950'], template="plotly_white")
        fig_hist.add_vline(x=p_mkt, line_color="red", line_dash="dash", annotation_text="SPOT PRICE")
        st.plotly_chart(fig_hist, use_container_width=True)

    with tabs[6]: # PESTAÑA: STRESS TEST (MACRO + BLACK SWAN RESTAURADOS)
        st.subheader("🌪️ Laboratorio de Resiliencia Macroeconómica")
        
        # Sliders Macro
        st.markdown("#### 1. Ajustes Granulares del Entorno")
        col_ma1, col_ma2 = st.columns(2)
        with col_ma1:
            m_rev = st.slider("Shock de Ingresos Reales (%)", -35, 10, 0)
            m_unemp = st.slider("Presión Desempleo (%)", 3, 18, 4)
        with col_ma2:
            m_infl = st.slider("Inflación CPI (%)", 0, 18, 3)
            m_wage = st.slider("Presión Salarial (%)", 0, 15, 4)
            
        # Black Swans
        st.markdown('''<div class="swan-box"><h3 style="color: #f85149; margin: 0;">⚠️ Eventos Cisne Negro (Black Swan)</h3>
            <p style="opacity: 0.8; margin-top:5px;">Seleccione eventos extremos para evaluar la robustez de la valoración.</p></div>''', unsafe_allow_html=True)
        
        sw1, sw2, sw3 = st.columns(3)
        g_swan_mod, w_swan_mod = 0.0, 0.0
        if sw1.checkbox("Conflicto Geopolítico"): g_swan_mod -= 0.07; w_swan_mod += 0.025
        if sw2.checkbox("Crisis de Suministros"): g_swan_mod -= 0.04; w_swan_mod += 0.012
        if sw3.checkbox("Ciberataque Sistémico"): g_swan_mod -= 0.05; w_swan_mod += 0.015
        
        # Impacto Integrado
        # El crecimiento g1 se ve afectado por ingresos, desempleo y cisnes.
        # El WACC se ve afectado por inflación, salarios y riesgo país (cisnes).
        g_stressed = g1_rate + (m_rev/100) - (m_unemp/500) + g_swan_mod
        w_stressed = wacc_rate + (m_infl/500) + (m_wage/1000) + w_swan_mod
        
        v_stress_res, _, _, _ = dcf_engine(fcf_base, g_stressed, g2_rate, w_stressed)
        
        st.markdown("---")
        st.metric("Fair Value Post-Stress", f"${v_stress_res:.2f}", f"{(v_stress_res/v_intrinsic-1)*100:.1f}% vs Escenario Base")
        st.info("Nota: Este modelo penaliza el crecimiento y aumenta el coste de capital según los riesgos macro seleccionados.")

    with tabs[7]: # PESTAÑA: OPCIONES LAB (FULL CONTROLS)
        st.subheader("📉 Derivados: Modelo Black-Scholes")
        ol1, ol2 = st.columns(2)
        with ol1:
            target_strike = st.number_input("Precio de Ejercicio (Strike)", value=float(round(p_mkt*1.05, 0)))
            expiry_days = st.slider("Días hasta la Expiración (T)", 1, 365, 45)
        with ol2:
            implied_vol = st.slider("Volatilidad Implícita (IV) %", 5, 150, 25) / 100
            risk_free = st.number_input("Tasa Libre de Riesgo (Risk-Free %)", value=4.5) / 100
            
        grks = calculate_full_greeks(p_mkt, target_strike, expiry_days/365, risk_free, implied_vol)
        
        st.markdown("---")
        # Visualización de Griegas
        o_m1, o_m2, o_m3, o_m4, o_m5 = st.columns(5)
        o_m1.metric("Precio Call", f"${grks['price']:.2f}")
        o_m2.metric("Delta Δ", f"{grks['delta']:.3f}")
        o_m3.metric("Gamma γ", f"{grks['gamma']:.4f}")
        o_m4.metric("Vega ν", f"{grks['vega']:.3f}")
        o_m5.metric("Theta θ", f"{grks['theta']:.2f}")
        
    with tabs[8]: # PESTAÑA: METODOLOGÍA
        st.header("Metodología de Valoración Institucional")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)")
        st.latex(r"K_e = R_f + \beta(R_m - R_f)")
        st.markdown("""
        **Glosario Técnico:**
        * **FCF Base:** Flujo de Caja Libre generado en el último año fiscal.
        * **WACC:** Coste Medio Ponderado del Capital utilizado para descontar flujos futuros.
        * **Valor Terminal:** Representa el valor de la empresa más allá de los 10 años proyectados.
        * **Griegas:** Medidas de sensibilidad del precio de una opción a cambios en el mercado.
        """)

if __name__ == "__main__":
    main()
