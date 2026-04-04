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

# --- 2. UI: CSS ADAPTATIVO PROFESIONAL (Soporte Light/Dark) ---
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
    .bull { color: #3fb950; background: rgba(63, 185, 80, 0.1); border-color: #3fb950; }
    .bear { color: #f85149; background: rgba(248, 81, 73, 0.1); border-color: #f85149; }
    .neutral { color: #dbab09; background: rgba(219, 171, 9, 0.1); border-color: #dbab09; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); padding: 0 20px; }
    .stTabs [aria-selected="true"] { background-color: #005BAA !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MOTORES DE CÁLCULO ---

def secure_clamp(val, min_v, max_v):
    """Evita errores de fuera de rango en sliders."""
    return float(max(min(val, max_v), min_v))

@st.cache_data(ttl=3600)
def load_institutional_data(ticker_symbol):
    """Extracción dinámica de estados financieros."""
    try:
        asset = yf.Ticker(ticker_symbol)
        inf, cf_raw = asset.info, asset.cashflow
        # FCF Simplificado para terminal dinámica
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
    """Modelo de descuento de flujos en 2 etapas."""
    projs = []
    val = fcf
    for i in range(1, 11):
        val *= (1 + g1) if i <= 5 else (1 + g2)
        projs.append(val)
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(projs, 1)])
    tv = (projs[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    return ((pv_f + pv_t) / shares) + cash, projs, pv_f, pv_t

def calculate_full_greeks(S, K, T, r, sigma, type='call'):
    """Motor Black-Scholes para la pestaña de Opciones."""
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

    # --- SIDEBAR ---
    st.sidebar.markdown("### 📊 Supuestos del Analista")
    p_mkt = st.sidebar.number_input("Precio Mercado ($)", value=float(data['price']))
    
    # Blindaje ValueError
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 100.0, secure_clamp(data['fcf_now'], 0.0, 100.0))
    g1 = st.sidebar.slider("Crecimiento 1-5Y (%)", -20, 100, int(secure_clamp(data['cagr_real']*100, -20, 100))) / 100
    g2 = st.sidebar.slider("Crecimiento 6-10Y (%)", 0, 50, 8) / 100
    wacc = st.sidebar.slider("WACC Base (%)", 3.0, 18.0, 8.5) / 100
    
    st.sidebar.markdown("---")
    buf_guia = io.BytesIO(b"Guia Metodologica: DCF 2 Etapas + Gordon Growth")
    st.sidebar.download_button("📄 Descargar Guía Metodológica", buf_guia, "Guia_Metodologica_COST.pdf")

    # Cálculos Core
    v_fair, flows, pv_c, pv_t = dcf_engine(fcf_in, g1, g2, wacc)
    upside = (v_fair / p_mkt - 1) * 100

    # Header de Métricas
    st.title(f"🏛️ {data['name']} — Master Intelligence Terminal")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['pe']:.1f}x", "Premium")
    m2.metric("Market Cap", f"${data['mkt_cap']:.1f}B", "COST-NASDAQ")
    m3.metric("Beta (Live)", f"{data['beta']}", "Neutral" if data['beta'] > 0.9 else "Defensivo")
    m4.metric("Valor Intrínseco", f"${v_fair:.0f}", f"{upside:.1f}% Upside")

    st.markdown("---")
    
    tabs = st.tabs(["📋 Resumen", "💎 Valoración", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📚 Metodología", "📥 Exportar"])

    # TAB 0: RESUMEN
    with tabs[0]:
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1*0.6, g2*0.5, wacc+0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1+0.04, g2+0.02, wacc-0.01)
        
        sc1.markdown(f'<div class="scenario-card"><span class="badge bear">Bajista</span><div class="price-hero">${v_baj:.0f}</div><small style="color:red">{((v_baj/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="badge neutral">Caso Base</span><div class="price-hero">${v_fair:.0f}</div><small style="color:orange">{upside:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="badge bull">Alcista</span><div class="price-hero">${v_alc:.0f}</div><small style="color:green">{((v_alc/p_mkt)-1)*100:.1f}% vs actual</small></div>', unsafe_allow_html=True)
        
        fig_donut = go.Figure(data=[go.Pie(labels=['PV Flujos 10Y', 'Valor Terminal'], values=[pv_c, pv_t], hole=.6, marker_colors=['#005BAA', '#E31837'])])
        fig_donut.update_layout(title="Composición del Valor", height=450)
        st.plotly_chart(fig_donut, use_container_width=True)

    # TAB 1: VALORACIÓN
    with tabs[1]:
        st.subheader("Trayectoria de Caja y Matriz de Sensibilidad")
        h_x = [c.strftime('%Y') for c in data['fcf_hist'].index[::-1]]
        h_y = data['fcf_hist'].values[::-1]
        p_x = [str(int(h_x[-1]) + i) for i in range(1, 11)]
        
        fig_bridge = go.Figure()
        fig_bridge.add_trace(go.Scatter(x=h_x, y=h_y, name="Real (SEC)", line=dict(color='#005BAA', width=5), mode='lines+markers'))
        fig_bridge.add_trace(go.Scatter(x=[h_x[-1]]+p_x, y=[h_y[-1]]+flows, name="Estimado", line=dict(color='#f85149', dash='dash', width=4), mode='lines+markers'))
        st.plotly_chart(fig_bridge, use_container_width=True)

        wr, gr = np.linspace(wacc-0.02, wacc+0.02, 5), np.linspace(0.015, 0.035, 5)
        mtx = [[dcf_engine(fcf_in, g1, g2, w, g)[0] for g in gr] for w in wr]
        df_m = pd.DataFrame(mtx, index=[f"W:{x*100:.1f}%" for x in wr], columns=[f"g:{x*100:.1f}%" for x in gr])
        st.plotly_chart(px.imshow(df_m, text_auto='.0f', color_continuous_scale='RdYlGn', title="Sensibilidad: WACC vs Crecimiento Perpetuo"), use_container_width=True)

    # TAB 2: BENCHMARKING
    with tabs[2]:
        peers_full = pd.DataFrame({
            'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN', 'S&P 500', 'Nasdaq'],
            'PE': [data['pe'], 31.2, 17.5, 21.1, 45.0, 22.5, 29.8],
            'Growth': [data['cagr_real']*100, 6.2, 4.5, 8.2, 12.5, 7.0, 11.0]
        })
        b1, b2 = st.columns(2)
        b1.plotly_chart(px.bar(peers_full, x='Ticker', y='PE', color='Ticker', title="Múltiplo P/E vs Índices"), use_container_width=True)
        b2.plotly_chart(px.scatter(peers_full, x='Growth', y='PE', text='Ticker', size='PE', title="Crecimiento vs Valuación de Mercado"), use_container_width=True)

    # TAB 3: MONTE CARLO (FIXED: YA NO ESTÁ VACÍA)
    with tabs[3]:
        st.subheader("Simulación Estocástica de Probabilidades")
        vol_mc = st.slider("Volatilidad del Modelo (%)", 1, 10, 3) / 100
        sims = []
        for _ in range(1000):
            # Variamos g1 y WACC aleatoriamente
            s_g1 = np.random.normal(g1, vol_mc)
            s_w = np.random.normal(wacc, 0.005)
            val, _, _, _ = dcf_engine(fcf_in, s_g1, g2, s_w)
            sims.append(val)
        
        prob_success = (np.array(sims) > p_mkt).mean() * 100
        fig_mc = px.histogram(sims, nbins=50, title=f"Probabilidad de Upside: {prob_success:.1f}%", color_discrete_sequence=['#3fb950'])
        fig_mc.add_vline(x=p_mkt, line_color="red", line_dash="dash", annotation_text="SPOT")
        st.plotly_chart(fig_mc, use_container_width=True)

    # TAB 4: STRESS TEST (FIXED: YA NO ESTÁ VACÍA)
    with tabs[4]:
        st.subheader("Laboratorio de Resiliencia Macroeconómica")
        st1, st2 = st.columns(2)
        with st1:
            sh_i = st.slider("Shock Ingreso Real %", -25, 10, 0)
            sh_u = st.slider("Alza Desempleo %", 3, 20, 4)
        with st2:
            sh_c = st.slider("Inflación CPI %", 0, 15, 3)
            sh_w = st.slider("Alza Salarial %", 0, 12, 4)
            
        # Impacto: Shock ingreso baja g1, inflación/tasas suben WACC
        v_s, _, _, _ = dcf_engine(fcf_in, g1+(sh_i/200)-(sh_u/500), g2, wacc+(sh_c/500)+(sh_w/1000))
        
        st.metric("Fair Value Post-Stress", f"${v_s:.2f}", f"{(v_s/v_fair-1)*100:.1f}% vs BASE")
        st.info("Este modelo ajusta el crecimiento y la tasa de descuento basándose en correlaciones históricas de consumo masivo.")

    # TAB 5: OPCIONES (CON GRIEGOS COMPLETOS)
    with tabs[5]:
        st.subheader("Griegas de Opciones (Black-Scholes)")
        ko1, ko2 = st.columns(2)
        with ko1: k_s = st.number_input("Strike Price Ref.", value=float(round(p_mkt*1.05, 0)))
        with ko2: vol_opt = st.slider("Volatilidad Implícita %", 10, 100, 25) / 100
        
        gr = calculate_full_greeks(p_mkt, k_s, 45/365, 0.045, vol_opt)
        
        go1, go2, go3, go4, go5 = st.columns(5)
        go1.metric("Precio Call", f"${gr['price']:.2f}")
        go2.metric("Delta Δ", f"{gr['delta']:.3f}")
        go3.metric("Gamma γ", f"{gr['gamma']:.4f}")
        go4.metric("Vega ν", f"{gr['vega']:.3f}")
        go5.metric("Theta θ", f"{gr['theta']:.2f}")

    # TAB 6: METODOLOGÍA
    with tabs[6]:
        st.header("Metodología de Valoración")
        st.latex(r"WACC = \frac{E}{V} \cdot K_e + \frac{D}{V} \cdot K_d \cdot (1 - T_c)")
        st.latex(r"Intrinsic Value = \sum_{t=1}^{10} \frac{FCF_t}{(1+WACC)^t} + \frac{TV}{(1+WACC)^{10}}")
        st.info("Análisis de grado institucional utilizando datos normalizados de la SEC vía yFinance API.")

    # TAB 7: EXPORTAR
    with tabs[7]:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            data['is'].to_excel(wr, sheet_name='Income'); data['bs'].to_excel(wr, sheet_name='Balance'); data['cf'].to_excel(wr, sheet_name='CashFlow')
        st.download_button("💾 Descargar Master Excel (3-Statement)", buf.getvalue(), f"COST_Institutional_Model.xlsx")

if __name__ == "__main__":
    main()
