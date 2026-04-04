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

# --- 2. UI: CSS ADAPTATIVO PROFESIONAL ---
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
    .scorecard-tile {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        height: 100%;
    }
    .tile-title { font-weight: 800; font-size: 0.9rem; color: #005BAA; text-transform: uppercase; margin-bottom: 8px; }
    .tile-value { font-size: 1.5rem; font-weight: 900; color: var(--text-main); }
    .scenario-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 15px; padding: 25px; text-align: center; margin-bottom: 20px;
    }
    .price-hero { font-size: 40px; font-weight: 900; color: var(--text-main); letter-spacing: -1px; }
    .badge { padding: 4px 12px; border-radius: 15px; font-weight: 700; font-size: 11px; text-transform: uppercase; border: 1px solid; display: inline-block; margin-bottom: 8px; }
    .swan-box { border: 2px dashed #f85149; padding: 15px; border-radius: 10px; background: rgba(248, 81, 73, 0.05); margin-top: 15px; }
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #003a70 100%);
        color: white !important; padding: 25px; border-radius: 20px; text-align: center;
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
            "price": inf.get('currentPrice', 950.0),
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
    price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2) if type=='call' else K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
    delta = norm.cdf(d1) if type=='call' else norm.cdf(d1) - 1
    return {"price": price, "delta": delta, "gamma": norm.pdf(d1)/(S*sigma*np.sqrt(T)), "vega": (S*np.sqrt(T)*norm.pdf(d1))/100, "theta": (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T))) - r*K*np.exp(-r*T)*norm.cdf(d1))/365}

# --- 4. LÓGICA PRINCIPAL ---

def main():
    data = load_institutional_data("COST")
    if not data: return

    # --- SIDEBAR ---
    st.sidebar.markdown("### 📊 Supuestos")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 150.0, secure_clamp(data['fcf_now'], 0.0, 150.0))
    g1 = st.sidebar.slider("Crecimiento Años 1-5 (%)", -30.0, 120.0, float(secure_clamp(data['cagr_real']*100, -30.0, 120.0))) / 100
    wacc = st.sidebar.slider("Tasa WACC (%)", 3.0, 20.0, 8.5) / 100

    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, 0.08, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # Header
    st.title(f"🏛️ {data['name']} Intelligence")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B")
    m3.metric("Beta", f"{data['beta']}", "Neutral")
    m4.metric("Fair Value", f"${v_fair:.0f}", f"{upside:.1f}%")

    st.markdown("---")
    
    # LISTA DE PESTAÑAS (Consolidada)
    tabs = st.tabs([
        "📋 Resumen", 
        "🛡️ Fundamental Scorecard", 
        "📊 Análisis Financiero Pro", 
        "💎 Valoración", 
        "📈 Benchmarking", 
        "🎲 Monte Carlo", 
        "🌪️ Stress Test", 
        "📉 Opciones",
        "📚 Metodología"
    ])

    with tabs[1]: # PESTAÑA SCORECARD
        st.subheader("Tablero de Salud (Tiles)")
        rec = data['recommendations']
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f'<div class="recommendation-hero"><small>CONSENSO</small><h1>{rec["key"]}</h1><div>Score: {rec["score"]}/5</div><hr><small>Target Price</small><h2>${rec["target"]:.2f}</h2></div>', unsafe_allow_html=True)
        with c2:
            st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=rec['score'], gauge={'axis':{'range':[1,5]}, 'steps':[{'range':[1,2],'color':"#3fb950"},{'range':[2,3],'color':"#dbab09"},{'range':[3,5],'color':"#f85149"}], 'bar':{'color':"white"}})), use_container_width=True)

    # --- NUEVA PESTAÑA: ANÁLISIS FINANCIERO PRO ---
    with tabs[2]:
        st.subheader("📈 Análisis de Ratios y Estados Financieros")
        
        # 1. Extracción de Ratios (Dinámica)
        is_df, bs_df = data['is'], data['bs']
        
        # Cálculos de Ratios
        gross_margin = (is_df.loc['Gross Profit'] / is_df.loc['Total Revenue']) * 100
        net_margin = (is_df.loc['Net Income'] / is_df.loc['Total Revenue']) * 100
        roe = (is_df.loc['Net Income'] / bs_df.loc['Stockholders Equity']) * 100
        current_ratio = bs_df.loc['Current Assets'] / bs_df.loc['Current Liabilities']
        
        ratios_df = pd.DataFrame({
            "Margen Bruto (%)": gross_margin,
            "Margen Neto (%)": net_margin,
            "ROE (%)": roe,
            "Liquidez Corriente": current_ratio
        }).T
        
        st.dataframe(ratios_df.style.format("{:.2f}"))

        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            # Ventas vs Utilidad Neta
            df_plot = is_df.loc[['Total Revenue', 'Net Income']].T
            fig_rev = px.line(df_plot, title="Evolución: Ventas vs Utilidad Neta", markers=True, template="plotly_white", color_discrete_map={"Total Revenue": "#005BAA", "Net Income": "#E31837"})
            st.plotly_chart(fig_rev, use_container_width=True)
            
            
        with col_g2:
            # Estructura de Márgenes
            fig_marg = px.bar(ratios_df.iloc[:2].T, barmode='group', title="Márgenes Operativos (%)", template="plotly_white")
            st.plotly_chart(fig_marg, use_container_width=True)

    with tabs[6]: # STRESS TEST (Black Swan Corrected)
        st.subheader("🌪️ Laboratorio de Stress Test")
        st.markdown('''<div class="swan-box"><h3 style="color: #f85149; margin: 0;">⚠️ Eventos Cisne Negro (Black Swan)</h3><p style="opacity: 0.8;">Simulación de eventos de baja probabilidad pero impacto extremo.</p></div>''', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        g_sw, w_sw = 0, 0
        if c1.checkbox("Guerra Geopolítica"): g_sw -= 0.06; w_sw += 0.025
        if c2.checkbox("Crisis Suministros"): g_sw -= 0.03; w_sw += 0.01
        
        v_s, _, _, _ = dcf_engine(fcf_in, g1+g_sw, 0.08, wacc+w_sw)
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}%")

    with tabs[8]: # METODOLOGÍA
        st.header("Metodología de Valoración")
        st.latex(r"WACC = \frac{E}{V} K_e + \frac{D}{V} K_d (1-T)")
        

if __name__ == "__main__": main()
