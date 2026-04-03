import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import norm
import yfinance as yf
import os
import io

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="COST Institutional Terminal", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.1); }
    .scenario-card { background-color: white; border-radius: 15px; padding: 20px; border: 1px solid #e0e0e0; text-align: center; color: #1c1c1c; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .metric-costco { color: #1c1c1c; font-size: 32px; font-weight: bold; margin: 5px 0; }
    .label-bajista { color: #d93025; background-color: #fce8e6; padding: 2px 10px; border-radius: 10px; font-weight: bold; font-size: 14px; }
    .label-base { color: #f29900; background-color: #fff4e5; padding: 2px 10px; border-radius: 10px; font-weight: bold; font-size: 14px; }
    .label-alcista { color: #188038; background-color: #e6f4ea; padding: 2px 10px; border-radius: 10px; font-weight: bold; font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTORES DE DATOS Y FINANZAS ---

@st.cache_data(ttl=3600)
def load_live_data(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        cf = t.cashflow
        price = info.get('currentPrice', 950.0)
        beta = info.get('beta', 0.79)
        # FCF = Op. Cash Flow + CapEx (CapEx suele venir negativo)
        fcf_series = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']) / 1e9
        f_vals = fcf_series.values[::-1]
        cagr = (f_vals[-1] / f_vals[0])**(1/(len(f_vals)-1)) - 1 if len(f_vals) > 1 else 0.12
        return {
            "precio": price, "beta": beta, "fcf_hist": fcf_series, "last_fcf": fcf_series.iloc[0], 
            "avg_growth": cagr, "name": info.get('longName', ticker_symbol),
            "is": t.financials, "bs": t.balance_sheet, "cf": cf
        }
    except:
        return {"precio": 950.0, "beta": 0.79, "last_fcf": 9.5, "avg_growth": 0.12, "fcf_hist": pd.Series([9.5, 8.5], index=pd.to_datetime(['2025-01-01', '2024-01-01'])), "name": "Costco Wholesale", "is": pd.DataFrame(), "bs": pd.DataFrame(), "cf": pd.DataFrame()}

def dcf_engine(fcf, g1, g2, wacc, gt, shares=0.44365, cash=22.0):
    flows = [fcf * (1 + g1)**i if i <= 5 else fcf * (1 + g1)**5 * (1 + g2)**(i-5) for i in range(1, 11)]
    pv_f = sum([f / (1 + wacc)**i for i, f in enumerate(flows, 1)])
    tv = (flows[-1] * (1 + gt)) / (wacc - gt)
    pv_t = tv / (1 + wacc)**10
    fair_v = ((pv_f + pv_t) / shares) + cash
    return fair_v, flows, pv_f, pv_t

def calculate_full_greeks(S, K, T, r, sigma, type='call'):
    T = max(T, 0.0001); d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T)); d2 = d1 - sigma * np.sqrt(T)
    if type == 'call': price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2); delta = norm.cdf(d1)
    else: price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1); delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T)); vega = (S * np.sqrt(T) * norm.pdf(d1)) / 100
    theta = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(d2 if type=='call' else -d2)) / 365
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# --- 3. DATOS DE MERCADO ---
PEERS_DATA = pd.DataFrame({'Ticker': ['COST', 'WMT', 'TGT', 'BJ', 'AMZN'], 'PE': [51.8, 31.2, 17.5, 21.1, 45.0], 'G': [9.5, 6.2, 4.5, 8.2, 12.5]})

# --- 4. INTERFAZ PRINCIPAL ---
def main():
    live = load_live_data("COST")
    st.title(f"🏛️ {live['name']} — Master Intelligence Terminal")
    st.caption("Terminal Dinámica 360 • Proyecciones Conectadas a la SEC")
    
    # --- SIDEBAR (CON BLINDAJE DE SEGURIDAD) ---
    st.sidebar.header("🎯 Supuestos Base")
    p_actual = st.sidebar.number_input("Precio Mercado ($)", value=float(live['precio']))
    
    # Lógica Clamping: Forzamos el valor a estar entre el mínimo y máximo del slider
    fcf_init = min(max(float(live['last_fcf']), 0.0), 50.0)
    g1_init = min(max(int(live['avg_growth']*100), 0), 40)
    
    fcf_in = st.sidebar.slider("FCF Base ($B)", 0.0, 50.0, fcf_init)
    g1_base = st.sidebar.slider("Crecimiento Años 1-5 (%)", 0, 40, g1_init) / 100
    g2_base = st.sidebar.slider("Crecimiento Años 6-10 (%)", 0, 20, 8) / 100
    wacc_base = st.sidebar.slider("WACC (%)", 5.0, 15.0, 8.5) / 100
    
    if os.path.exists("Guia_Metodologica_COST.pdf"):
        with open("Guia_Metodologica_COST.pdf", "rb") as f:
            st.sidebar.download_button("📄 Guía Metodológica", f, "Guia_Metodologica_COST.pdf")

    # CÁLCULOS
    v_base, flows, pv_f, pv_t = dcf_engine(fcf_in, g1_base, g2_base, wacc_base, 0.025)

    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P/E TTM", "51.8x"); c2.metric("Market Cap", "$450.2B"); c3.metric("Beta", f"{live['beta']}"); c4.metric("Valor Est.", f"${v_base:.0f}", f"{(v_base/p_actual-1)*100:.1f}%")

    st.markdown("---")
    tabs = st.tabs(["📋 Resumen", "💎 Valoración", "📊 Benchmarking", "🎲 Monte Carlo", "🌪️ Stress Test", "📉 Opciones", "📥 Exportar"])

    with tabs[0]: # Resumen
        sc1, sc2, sc3 = st.columns(3)
        v_baj, _, _, _ = dcf_engine(fcf_in, g1_base*0.5, g2_base*0.4, wacc_base+0.02, 0.02)
        v_alc, _, _, _ = dcf_engine(fcf_in, g1_base+0.03, g2_base+0.02, wacc_base-0.015, 0.03)
        sc1.markdown(f'<div class="scenario-card"><span class="label-bajista">Bajista</span><div class="metric-costco">${v_baj:.0f}</div></div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="scenario-card"><span class="label-base">Caso Base</span><div class="metric-costco">${v_base:.0f}</div></div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="scenario-card"><span class="label-alcista">Alcista</span><div class="metric-costco">${v_alc:.0f}</div></div>', unsafe_allow_html=True)
        st.plotly_chart(go.Figure(data=[go.Pie(labels=['Flujos 10Y', 'Valor Terminal'], values=[pv_f, pv_t], hole=.6, marker_colors=['#005BAA', '#E31837'])]), use_container_width=True)

    with tabs[1]: # Valoración (Puente de Flujos)
        h_x = [c.strftime('%Y') for c in live['fcf_hist'].index[::-1]]
        h_y = live['fcf_hist'].values[::-1]
        fig_b = go.Figure()
        fig_b.add_trace(go.Scatter(x=h_x, y=h_y, name="Histórico Real", line=dict(color='#005BAA', width=4)))
        fig_b.add_trace(go.Scatter(x=[h_x[-1]] + [str(int(h_x[-1])+i) for i in range(1,11)], y=[h_y[-1]] + flows, name="Proyección", line=dict(dash='dash', color='#E31837')))
        st.plotly_chart(fig_b, use_container_width=True)
        w_r = np.linspace(wacc_base-0.02, wacc_base+0.02, 5); g_r = np.linspace(0.015, 0.035, 5)
        m = [[dcf_engine(fcf_in, g1_base, g2_base, wr, gr)[0] for gr in g_r] for wr in w_r]
        st.plotly_chart(px.imshow(pd.DataFrame(m, index=[f"W:{x*100:.1f}%" for x in w_r], columns=[f"g:{x*100:.1f}%" for x in g_r]), text_auto='.0f', color_continuous_scale='RdYlGn'), use_container_width=True)

    with tabs[2]: # Benchmarking
        bc1, bc2 = st.columns(2)
        bc1.plotly_chart(px.bar(PEERS_DATA, x='Ticker', y='PE', color='Ticker', title="P/E Comparativo"), use_container_width=True)
        bc2.plotly_chart(px.scatter(PEERS_DATA, x='Rev_Growth', y='PE', text='Ticker', size='PE', title="Crecimiento vs Valuación"), use_container_width=True)

    with tabs[3]: # Monte Carlo
        sims = [dcf_engine(fcf_in, np.random.normal(g1_base, 0.02), g2_base, np.random.normal(wacc_base, 0.005), 0.025)[0] for _ in range(1000)]
        st.plotly_chart(px.histogram(sims, title=f"Probabilidad de Éxito: {(np.array(sims) > p_actual).mean()*100:.1f}%", color_discrete_sequence=['#005BAA']), use_container_width=True)

    with tabs[4]: # Stress Test
        st1, st2 = st.columns(2)
        with st1: s_i = st.slider("Ingreso Disponible %", -10, 5, 0); s_u = st.slider("Desempleo %", 3, 15, 4)
        with st2: s_c = st.slider("Inflación %", 0, 10, 3); s_w = st.slider("Alza Salarial %", 0, 8, 4)
        v_s, _, _, _ = dcf_engine(fcf_in, g1_base+(s_i/200)-(s_u/500), g2_base, wacc_base+(s_c/500)+(s_w/1000), 0.025)
        st.metric("Valor Post-Estrés", f"${v_s:.2f}", f"{(v_s/v_base-1)*100:.1f}%")

    with tabs[5]: # Opciones
        k = st.number_input("Strike", value=float(round(p_actual*1.05, 0))); iv = st.slider("Volatilidad %", 5, 100, 25)/100
        r = calculate_full_greeks(p_actual, k, 30/365, 0.045, iv, 'call')
        st.metric("Precio Call", f"${r['price']:.2f}"); st.write(f"**Delta:** {r['delta']:.3f} | **Vega:** {r['vega']:.3f}")

    with tabs[6]: # Exportar
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
            live['is'].to_excel(wr, sheet_name='Income'); live['bs'].to_excel(wr, sheet_name='Balance'); live['cf'].to_excel(wr, sheet_name='CashFlow')
        st.download_button("🟢 Descargar Excel 3-Statement", buf.getvalue(), "Modelo_COST_Full.xlsx")

if __name__ == "__main__":
    main()
