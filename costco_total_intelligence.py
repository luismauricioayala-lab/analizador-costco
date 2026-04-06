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
from plotly.subplots import make_subplots
import plotly.io as pio
from curl_cffi import requests # <--- INTEGRACIÓN FASE 2: SUPLANTACIÓN DE NAVEGADOR

pd.options.display.float_format = '{:,.2f}'.format
pio.templates["bloomberg_fix"] = pio.templates["plotly_dark"]
# 1. Forzar comas en el eje Y de cualquier gráfico
pio.templates["bloomberg_fix"].layout.yaxis.tickformat = ",.0f"
# 2. Forzar comas en el eje X de cualquier gráfico
pio.templates["bloomberg_fix"].layout.xaxis.tickformat = ",.0f"
# 3. EL TRUCO PARA LA MATRIZ: Forzar formato de etiquetas internas
pio.templates["bloomberg_fix"].layout.annotationdefaults.font.size = 10
# Establecer como predeterminado
pio.templates.default = "bloomberg_fix"

# =============================================================================
# 1. ARQUITECTURA DE CONFIGURACIÓN Y UI (ESTÉTICA BLOOMBERG ULTIMATE)
# =============================================================================

st.set_page_config(
    page_title="COST Institutional Terminal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "Terminal Institucional Costco v2026.04"
    }
)

# Inyección de CSS de Grado Bancario: Soporte Total Temas Light/Dark
st.markdown("""
    <style>
    :root {
        --accent-blue: #005BAA;
        --accent-gold: #D4AF37;
        --danger-red: #f85149;
        --success-green: #3fb950;
        --bg-card: var(--secondary-background-color);
        --text-color: var(--text-color);
        --border-color: var(--border-color);
    }
    
    /* Tiles de métricas con profundidad */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 30px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
        transition: all 0.4s ease;
    }
    div[data-testid="stMetric"]:hover { transform: translateY(-8px); border-color: var(--accent-blue); }

    /* Pestañas (Tabs) de Grado Industrial con indicador activo grueso */
    .stTabs [data-baseweb="tab-list"] { gap: 15px; border-bottom: 2px solid var(--border-color); }
    .stTabs [data-baseweb="tab"] {
        height: 75px; 
        background-color: var(--bg-card);
        border-radius: 15px 15px 0 0; 
        padding: 0 45px; 
        font-weight: 800;
        font-size: 16px;
        color: var(--text-color);
        border: 1px solid var(--border-color);
    }
    .stTabs [aria-selected="true"] { 
        border-bottom: 6px solid var(--accent-blue) !important;
        background-color: rgba(0, 91, 170, 0.15) !important;
        color: var(--accent-blue) !important;
    }

    /* Caja de Cisne Negro (Black Swan Matrix) */
    .swan-box {
        border: 4px dashed var(--danger-red);
        padding: 45px; border-radius: 30px;
        background: rgba(248, 81, 73, 0.08); margin: 30px 0;
    }
    
    /* Diagnóstico IA / Estrellas */
    .conclusion-item {
        display: flex; align-items: center; padding: 22px 35px;
        border-bottom: 1px solid var(--border-color);
        background: var(--bg-card); border-radius: 18px; margin-bottom: 18px;
        transition: all 0.3s;
    }
    .conclusion-item:hover { transform: translateX(10px); background: rgba(128,128,128,0.05); }
    .icon-box { margin-right: 30px; font-size: 2.2rem; min-width: 60px; text-align: center; }
    
    /* Hero de Recomendación Bloomberg */
    .recommendation-hero {
        background: linear-gradient(135deg, #005BAA 0%, #002d58 100%);
        color: white !important; padding: 65px; border-radius: 35px; text-align: center;
        box-shadow: 0 30px 70px rgba(0,0,0,0.6);
    }

/* === TARJETAS DE ESCENARIO REFINADAS (SOBER IMPACT) === */
    .scenario-card-detailed {
        padding: 30px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        border: 1px solid var(--border-color);
        background-color: var(--bg-card); /* Fondo neutro */
        transition: all 0.2s ease;
    }
    .scenario-card-detailed:hover { border-color: var(--accent-blue); }

    /* Indicadores sutiles en la parte superior */
    .bear-pro { border-top: 4px solid #f85149; background: rgba(248, 81, 73, 0.03); }
    .base-pro { border-top: 4px solid #005BAA; background: rgba(0, 91, 170, 0.03); }
    .bull-pro { border-top: 4px solid #3fb950; background: rgba(63, 185, 80, 0.03); }

    .price-hero-sober { 
        font-size: 48px; 
        font-weight: 800; 
        margin: 10px 0; 
        letter-spacing: -1px;
    }
    .scenario-label-sober { 
        font-size: 12px; 
        font-weight: 700; 
        text-transform: uppercase; 
        color: var(--text-color); 
        opacity: 0.7;
        letter-spacing: 1.2px; 
    }
    .driver-list-sober { 
        font-size: 13px; 
        color: var(--text-color); 
        opacity: 0.8;
        margin-top: 15px; 
        line-height: 1.6; 
        text-align: left; 
        border-top: 1px solid var(--border-color);
        padding-top: 15px;
    }

/* Widget de Recomendación v4 - Datos de Alta Precisión */
    .row-v3 {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        font-size: 0.85rem;
        height: 26px;
    }
    .lbl-v3 {
        width: 110px; 
        color: #bdc3c7;
        font-weight: 500;
        white-space: nowrap;
    }
    .bar-bg-v3 {
        flex-grow: 1;
        background-color: #2c3e50;
        height: 8px;
        margin: 0 12px;
        border-radius: 4px;
        position: relative;
    }
    .bar-fill-v3 { height: 100%; border-radius: 4px; }
    .pct-v3 {
        width: 85px; /* Espacio para "XX (XX.X%)" */
        text-align: right;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        font-weight: 600;
        color: #ecf0f1;
    }
    
    /* Tablas de Auditoría */
    .stTable { font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 2. MOTOR DE INTELIGENCIA DE DATOS (SEC AUDIT ENGINE + BÚNKER FALLBACK)
# =============================================================================

class InstitutionalDataService:
    """Clase maestra para la adquisición y normalización de datos auditados COST."""
    
    @staticmethod
    @st.cache_data(ttl=3600)
    def fetch_verified_payload(ticker):
        """Descarga de datos con sistema de Búnker (CSV Local) si Yahoo falla."""
        archivo_local = f"{ticker}.csv"
        
        try:
            # INTENTO 1: Yahoo Finance con curl_cffi integrado
            asset = yf.Ticker(ticker)
            info = asset.info
            cf = asset.cashflow
            is_stmt = asset.financials
            bs = asset.balance_sheet
            
            if cf.empty or is_stmt.empty:
                raise ValueError("Yahoo devolvió estados vacíos.")

            # Cálculo de FCF Real (Tu lógica exacta)
            fcf_raw = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure'])
            fcf_now = fcf_raw.iloc[0] / 1e9

        except Exception as e:
            st.warning(f"⚠️ Yahoo restringido para {ticker}. Accediendo al Búnker local...")
            
            # FALLBACK: Carga desde el búnker de archivos que descargaste
            if os.path.exists(archivo_local):
                st.info(f"🏛️ Modo Offline Activado: Usando {archivo_local}")
                
                df_bunker = pd.read_csv(archivo_local, index_col=0, parse_dates=True)
                ultimo_precio = float(df_bunker['Close'].iloc[-1])
                
                # Calculamos el min y max real de tu archivo CSV para la barra
                min_52w = float(df_bunker['Low'].tail(252).min()) # 252 días = 1 año bursátil
                max_52w = float(df_bunker['High'].tail(252).max())

                return {
                    "info": {
                        "currentPrice": ultimo_precio, 
                        "shortName": "Costco Wholesale", 
                        "symbol": ticker,
                        "trailingEps": 16.5,
                        "fiftyTwoWeekLow": min_52w, 
                        "fiftyTwoWeekHigh": max_52w 
                    },
                    "price": ultimo_precio,
                    "mkt_cap_b": 450.0,
                    "fcf_now_b": 9.5,
                    "fcf_hist_b": pd.Series([8.0, 8.5, 9.0, 9.5]),
                    "beta": 0.98,
                    "shares_m": 443.6,
                    "cash_b": 22.0,
                    "debt_b": 9.0,
                    "hist_years": ["2023", "2024", "2025"],
                    "rev_vals": [220, 240, 250],
                    "ebitda_vals": [15, 17, 18],
                    "ni_vals": [6, 7, 8],
                    "eps_vals": 16.5,
                    "acc_summary": {
                        "Revenue ($B)": 250.0, "EBITDA ($B)": 18.0, "Net Income ($B)": 8.0,
                        "ROE (%)": 28.0, "Debt/Equity": 45.0, "Current Ratio": 1.05, "Operating Margin (%)": 3.5
                    },
                    "analysts": {"key": "BUY", "score": 2.0, "target": 1060.0, "count": 37}
                }
            else:
                st.error(f"❌ Error crítico: No se encontraron datos para {ticker}")
                return None

        # Procesamiento de Cuadro de 3 Años (Mantenemos tu lógica exacta si el try tiene éxito)
        is_3y = is_stmt.iloc[:, :3]
        hist_years = is_3y.columns.year.astype(str).tolist()
        rev_vals = (is_3y.loc['Total Revenue'] / 1e9).tolist()
        ebitda_vals = (is_3y.loc['EBITDA'] / 1e9).tolist()
        ni_vals = (is_3y.loc['Net Income'] / 1e9).tolist()
        eps_vals = info.get('trailingEps', 16.5)

        acc_summary = {
            "Revenue ($B)": info.get('totalRevenue', 0) / 1e9,
            "EBITDA ($B)": info.get('ebitda', 0) / 1e9,
            "Net Income ($B)": info.get('netIncomeToCommon', 0) / 1e9,
            "ROE (%)": info.get('returnOnEquity', 0.28) * 100,
            "Debt/Equity": info.get('debtToEquity', 45.0),
            "Current Ratio": info.get('currentRatio', 1.05),
            "Operating Margin (%)": info.get('operatingMargins', 0.035) * 100
        }

        return {
            "info": info, "is": is_stmt, "bs": bs, "cf": cf,
            "fcf_now_b": fcf_now, "fcf_hist_b": fcf_raw / 1e9,
            "price": info.get('currentPrice', 1014.96),
            "mkt_cap_b": info.get('marketCap', 450e9) / 1e9,
            "beta": info.get('beta', 0.978),
            "shares_m": info.get('sharesOutstanding', 443.6e6) / 1e6,
            "cash_b": info.get('totalCash', 22e9) / 1e9,
            "debt_b": info.get('totalDebt', 9e9) / 1e9,
            "hist_years": hist_years, "rev_vals": rev_vals, 
            "ebitda_vals": ebitda_vals, "ni_vals": ni_vals, "eps_vals": eps_vals,
            "acc_summary": acc_summary,
            "analysts": {
                "key": info.get('recommendationKey', 'BUY').upper(),
                "score": info.get('recommendationMean', 2.0),
                "target": info.get('targetMeanPrice', 1067.59),
                "count": info.get('numberOfAnalystOpinions', 37)
            }
        }

    @staticmethod
    @st.cache_data(ttl=3600)
    def fetch_peer_group_data(ticker_list):
        """Versión de Diagnóstico y Carga Blindada."""
        archivo_offline = "peers_stats.csv"
        
        # Agregamos COST a la lista de búsqueda para que no se pierda en el búnker
        full_search_list = ticker_list + ["COST"]
        
# --- 2. CARGA FORZOSA DEL BÚNKER ---
        df_final = None
        if os.path.exists(archivo_offline):
            try:
                df_final = pd.read_csv(archivo_offline)
                # Limpieza de columnas y tickers
                df_final.columns = df_final.columns.str.strip()
                if 'Ticker' in df_final.columns:
                    df_final['Ticker'] = df_final['Ticker'].astype(str).str.strip()
                
                if not df_final.empty:
                    # FILTRADO CRUCIAL: Ahora incluimos a Costco
                    df_final = df_final[df_final['Ticker'].isin(full_search_list)]
                    if not df_final.empty:
                        return df_final
            except Exception as e:
                st.error(f"❌ Error en Búnker: {e}")

        # --- 3. INTENTO ONLINE (SI EL BÚNKER NO TIENE DATOS) ---
        try:
            peer_results = []
            for t in full_search_list:
                asset = yf.Ticker(t)
                info = asset.info
                # Verificamos que info exista y tenga datos mínimos para no romper el DataFrame
                if info and isinstance(info, dict) and 'marketCap' in info:
                    peer_results.append({
                        "Ticker": t,
                        "Nombre": info.get('shortName', t),
                        "Mkt Cap ($B)": info.get('marketCap', 0) / 1e9,
                        "P/E Ratio": info.get('trailingPE', 0),
                        "EV/EBITDA": info.get('enterpriseToEbitda', 0),
                        "EV/FCF": info.get('enterpriseValue') / info.get('freeCashflow'),
                        "ROE (%)": info.get('returnOnEquity', 0) * 100,
                        "Net Margin (%)": info.get('profitMargins', 0) * 100,
                        "Rev Growth (%)": info.get('revenueGrowth', 0) * 100
                    })
            
            if peer_results:
                return pd.DataFrame(peer_results)
        except Exception as e:
            # Silenciamos el error para que no bloquee la UI si Yahoo falla
            pass

        return df_final
        
class ValuationOracle:
    """Implementación de modelos financieros DCF y Black-Scholes."""
    @staticmethod
    def run_macro_dcf(fcf, g1, g2, wacc, tg=0.025, shares=443.6, cash=22.0, debt=9.0, macro_adj=0.0):
        # 1. VALIDACIÓN DE CONVERGENCIA
        if wacc <= tg:
            return float('nan'), 0.0, 0.0, []

        # 2. Ajuste inicial por entorno macro
        adj_base = fcf * (1 + macro_adj)
        projs, df_flows = [], []
        curr = adj_base
        
        # 3. Proyección de flujos (10 años)
        for i in range(1, 6):
            curr *= (1 + g1)
            projs.append(curr)
            df_flows.append(curr / (1 + wacc)**i)
            
        for i in range(6, 11):
            curr *= (1 + g2)
            projs.append(curr)
            df_flows.append(curr / (1 + wacc)**i)
            
        # 4. Cálculos de Valor Presente
        pv_f = sum(df_flows)
        tv = (projs[-1] * (1 + tg)) / (wacc - tg)
        pv_t = tv / (1 + wacc)**10
        
        # 5. Equity Value y Precio Fair Value
        equity_v = pv_f + pv_t + cash - debt
        fair_p = (equity_v / shares) * 1000
        
        return fair_p, pv_f, pv_t, projs
        
    @staticmethod
    def calculate_full_greeks(S, K, T, r, sigma, o_type='call'):
        """Modelo Black-Scholes con Griegas Integrales."""
        T = max(T, 0.0001)
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        cp = 1 if o_type == 'call' else -1
        
        price = cp * (S * norm.cdf(cp * d1) - K * np.exp(-r * T) * norm.cdf(cp * d2))
        delta = norm.cdf(d1) if o_type == 'call' else norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = (S * np.sqrt(T) * norm.pdf(d1)) / 100
        theta = (-(S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))) - r * K * np.exp(-r * T) * norm.cdf(cp * d2)) / 365
        
        return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

# =============================================================================
# 4. INTERFAZ DE USUARIO Y CONTROL DE PANELES (MAIN)
# =============================================================================

def main():
    # --- INTERCEPTOR MAESTRO (VERSIÓN FINAL ANTI-ERRORES) ---
    def patched_plotly_chart(fig, use_container_width=True, **kwargs):
        try:
            # 1. Aplicar el tema oscuro
            fig.update_layout(template="plotly_dark", hoverformat="$,.2f")
            
            # 2. Forzar comas y $ en el eje Y de forma aislada
            fig.update_yaxes(tickformat="$,.0f")
            
            # 3. Forzar comas en el eje X (si es numérico)
            fig.update_xaxes(tickformat=",.0f")
            
            # 4. EL MARTILLO PARA EL HEATMAP (Tu matriz verde/roja)
            # Solo aplica si el gráfico tiene trazas tipo heatmap
            fig.update_traces(
                texttemplate="$%{z:,.0f}", 
                selector=dict(type='heatmap')
            )
        except Exception:
            # Si algún gráfico no es compatible con este formato, 
            # lo deja pasar sin romper la app
            pass
            
        # Usamos st.write para evitar bucles infinitos y renderizar Plotly
        return st.write(fig)

    # REEMPLAZO GLOBAL
    st.plotly_chart = patched_plotly_chart
    
    # 1. Adquisición de Datos (Dentro de main para evitar NameError)
    data = InstitutionalDataService.fetch_verified_payload("COST")
    if not data: 
        st.error("No se pudieron cargar los datos de la API.")
        return    
# -------------------------------------------------------------------------
    # 2. SIDEBAR: PANEL DE CONTROL DIRECTO
    # -------------------------------------------------------------------------
    st.sidebar.title("🏛️ Master Control")
    
    # Referencia de precio base
    p_ref = st.sidebar.number_input("Market Price Ref. ($)", value=float(data['price']), step=0.01, format="%.2f")

    st.sidebar.divider()
    
    # --- SECCIÓN 1: VALUACIÓN CORE ---
    st.sidebar.subheader("1. Valuación (DCF)")
    wacc_base = st.sidebar.slider("Tasa WACC Base (%)", 4.0, 16.0, 6.5) / 100
    g1_in = st.sidebar.slider("Crecimiento 1-5Y (%)", -10.0, 50.0, 12.0) / 100
    g2_in = st.sidebar.slider("Crecimiento 6-10Y (%)", 0.0, 20.0, 8.0) / 100
    g_terminal = st.sidebar.slider("Crecimiento Perpetuo (%)", 1.0, 5.0, 3.5) / 100

    st.sidebar.divider()

    # --- SECCIÓN 2: LABORATORIO MACRO (DESPLEGADO) ---
    st.sidebar.subheader("2. Laboratorio Macroeconómico")
    u_rate = st.sidebar.slider("Tasa de Desempleo (%)", 3.0, 18.0, 4.2)
    income_g = st.sidebar.slider("Crec. Ingreso Disponible (%)", -12.0, 12.0, 2.5) / 100
    inflation = st.sidebar.slider("Inflación CPI (%)", 0.0, 15.0, 3.2) / 100
    fed_rates = st.sidebar.slider("Variación Fed Rates (bps)", -200, 500, 0) / 10000

    st.sidebar.markdown("**PIB Blended (Ponderado)**")
    gdp_us = st.sidebar.slider("PIB EE.UU (%)", -5.0, 8.0, 2.3) / 100
    gdp_ca = st.sidebar.slider("PIB Canadá (%)", -5.0, 8.0, 2.1) / 100
    gdp_intl = st.sidebar.slider("PIB Internacional (%)", -5.0, 8.0, 3.0) / 100

    # --- LÓGICA DE CÁLCULO INSTANTÁNEO ---
    blended_gdp = (gdp_us * 0.73) + (gdp_ca * 0.14) + (gdp_intl * 0.13)
    macro_adj = (income_g * 1.5) + (blended_gdp * 0.8) - (inflation * 1.2)
    final_wacc = wacc_base + fed_rates 

    # --- MOTOR DE VALORACIÓN ---
    if final_wacc <= g_terminal:
        f_val, pv_f, pv_t, flows = float('nan'), 0.0, 0.0, []
        upside = 0.0
    else:
        f_val, pv_f, pv_t, flows = ValuationOracle.run_macro_dcf(
            data['fcf_now_b'], g1_in, g2_in, final_wacc, g_terminal,
            shares=data['shares_m'], cash=data['cash_b'], debt=data['debt_b'], 
            macro_adj=macro_adj
        )
        upside = (f_val / p_ref - 1) * 100 if p_ref > 0 else 0.0

    st.sidebar.divider()
    st.sidebar.caption("🚀 Terminal Reactiva: Todos los cambios impactan en tiempo real.")

    # 4. Cabecera con Lógica Beta Neutro
    st.title(f"🏛️ {data['info'].get('longName')} Institutional Terminal")
    st.caption(f"Sync SEC 2026 | Build: v2026.04.06 | GDP Blended: {blended_gdp*100:.3f}% | WACC: {final_wacc*100:.2f}%")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P/E TTM", f"{data['info'].get('trailingPE', 52.9):.1f}x", "Premium Valuation")
    m2.metric("Mkt Cap", f"${data['mkt_cap_b']:,.1f}B", "NASDAQ: COST")
    
    b_val = data['beta']
    b_label, b_color = ("Market Neutral", "off") if 0.95 <= b_val <= 1.05 else (("Low Vol", "normal") if b_val < 0.95 else ("High Vol", "inverse"))
    m3.metric("Riesgo Beta", f"{b_val:.3f}", b_label, delta_color=b_color)
    m4.metric("Intrinsic Value", f"${f_val:,.2f}", f"{upside:+.1f}%", delta_color="normal" if upside > 0 else "inverse")

    st.markdown("---")

    # 5. ARQUITECTURA DE PESTAÑAS
    tabs = st.tabs([
        "📋 Resumen", "🛡️ Scorecard & Radar", "🔬 Peer Analysis", "💰 Ganancias", "🌪️ Stress Test Pro", 
        "📈 Forward Looking", "📊 Finanzas Pro", "💎 DCF Lab Pro", "🎲 Monte Carlo", "🔬 Comparativa APT", "📜 Metodología", "📈 Opciones Lab"
    ])

    # A partir de aquí ya puedes seguir con tus 'with tabs[0]:', etc.
    # RECUERDA: En Tab 1 usa: y=[pv_f, pv_t, data['cash_b'] - data['debt_b'], equity_val_b]

# -------------------------------------------------------------------------
    # TAB 1: RESUMEN EJECUTIVO (VERSIÓN INSTITUCIONAL BLINDADA)
    # -------------------------------------------------------------------------
    with tabs[0]:
        # === NUEVO MÓDULO: CONTEXTO DE MERCADO 52 SEMANAS ===
        low52 = data['info'].get('fiftyTwoWeekLow', 1.0)
        high52 = data['info'].get('fiftyTwoWeekHigh', 1.0)
        curr_p = data['price']
        
        # Cálculo de la posición del precio actual en el rango (0% a 100%)
        pos_52 = ((curr_p - low52) / (high52 - low52)) * 100 if high52 > low52 else 0
        
        st.subheader("Contexto de Mercado: Rango 52 Semanas")
        c_r1, c_r2 = st.columns([1, 2.5])
        
        with c_r1:
            st.metric("Cotización Actual", f"${curr_p:,.2f}")
            
        with c_r2:
            # Barra visual de 52 semanas (estilo Bloomberg)
            st.markdown(f"""
                <div style="margin-top:10px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; opacity: 0.9;">
                        <span>Mín. 52W: <b>${low52:,.2f}</b></span>
                        <span>Máx. 52W: <b>${high52:,.2f}</b></span>
                    </div>
                    <div style="background: #333; height: 14px; border-radius: 7px; margin-top: 8px; position: relative; border: 1px solid var(--border-color);">
                        <div style="background: linear-gradient(90deg, #005BAA, #00A3E0); width: {pos_52}%; height: 100%; border-radius: 7px;"></div>
                        <div style="position: absolute; left: {pos_52}%; top: -5px; height: 24px; width: 4px; background: white; border-radius: 2px; box-shadow: 0 0 10px rgba(255,255,255,0.5);"></div>
                    </div>
                    <p style="font-size: 0.75rem; text-align: center; margin-top: 10px; opacity: 0.7;">
                        La acción se encuentra al <b>{pos_52:.1f}%</b> de su rango anual.
                    </p>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---") # Separador visual
        
        st.subheader("Análisis de Sensibilidad de Escenarios (Target 2026)")
        
        # 1. Normalización de Flujos (Owner Earnings)
        fcf_now = data.get('fcf_now_b', 0)
        fcf_premium = fcf_now * 1.25 
        
        # --- VALIDACIÓN GLOBAL DE CONVERGENCIA ---
        if final_wacc <= g_terminal:
            st.error(f"🚨 **MODELO INESTABLE:** El WACC Base ({final_wacc*100:.2f}%) es menor o igual al Crecimiento Terminal ({g_terminal*100:.2f}%)")
            st.info("Ajusta los parámetros en el sidebar (sube el WACC o baja el G Terminal) para que la tasa de descuento supere al crecimiento perpetuo.")
        else:
            # --- CÁLCULO DE ESCENARIOS CON DESGLOSE DE DRIVERS ---
            
            # A. ESCENARIO BAJISTA (BEAR)
            bear_wacc = final_wacc + 0.005
            bear_g1 = g1_in * 0.90
            bear_gt = g_terminal - 0.005
            bear_macro = macro_adj - 0.02
            # Aquí raramente habrá error porque el WACC sube y el G baja
            v_bear, _, _, _ = ValuationOracle.run_macro_dcf(
                fcf_premium, bear_g1, g2_in * 0.90, bear_wacc, bear_gt, macro_adj=bear_macro
            )
            
            # B. ESCENARIO BASE (INTRINSIC)
            v_base, pv_f, pv_t, _ = ValuationOracle.run_macro_dcf(
                fcf_premium, g1_in, g2_in, final_wacc, g_terminal, macro_adj=macro_adj
            )
            
            # C. ESCENARIO ALCISTA (BULL)
            bull_wacc = final_wacc - 0.005
            bull_g1 = g1_in * 1.15
            bull_gt = g_terminal + 0.005
            bull_macro = macro_adj + 0.03
            
            # VALIDACIÓN ESPECÍFICA PARA BULL (El escenario que suele dar $nan)
            if bull_wacc <= bull_gt:
                v_bull = float('nan')
                bull_display = "N/A"
                bull_color = "#888888" # Gris si no hay convergencia
            else:
                v_bull, _, _, _ = ValuationOracle.run_macro_dcf(
                    fcf_premium, bull_g1, g2_in * 1.15, bull_wacc, bull_gt, macro_adj=bull_macro
                )
                bull_display = f"${v_bull:,.0f}"
                bull_color = "#3fb950"

            # --- RENDERIZADO DE TARJETAS (ESTILO BLOOMBERG PRO) ---
            c_sc1, c_sc2, c_sc3 = st.columns(3)
            
            with c_sc1:
                st.markdown(f"""<div class="scenario-card-detailed bear-pro">
                    <div class="scenario-label-sober">Escenario Bajista (Bear)</div>
                    <div class="price-hero-sober" style="color:#f85149">${v_bear:,.0f}</div>
                    <div class="driver-list-sober">
                        • <b>WACC:</b> {bear_wacc*100:.2f}% (Riesgo ↑)<br>
                        • <b>Crec. 1-5Y:</b> {bear_g1*100:.1f}%<br>
                        • <b>G. Terminal:</b> {bear_gt*100:.1f}%<br>
                        • <b>Impacto Macro:</b> {bear_macro*100:.1f}%
                    </div>
                </div>""", unsafe_allow_html=True)
                
            with c_sc2:
                st.markdown(f"""<div class="scenario-card-detailed base-pro">
                    <div class="scenario-label-sober">Escenario Base (Intrinsic)</div>
                    <div class="price-hero-sober" style="color:var(--text-color)">${v_base:,.0f}</div>
                    <div class="driver-list-sober">
                        • <b>WACC:</b> {final_wacc*100:.2f}% (Market)<br>
                        • <b>Crec. 1-5Y:</b> {g1_in*100:.1f}%<br>
                        • <b>G. Terminal:</b> {g_terminal*100:.1f}%<br>
                        • <b>Impacto Macro:</b> {macro_adj*100:.1f}%
                    </div>
                </div>""", unsafe_allow_html=True)
                
            with c_sc3:
                st.markdown(f"""<div class="scenario-card-detailed bull-pro">
                    <div class="scenario-label-sober">Escenario Alcista (Bull)</div>
                    <div class="price-hero-sober" style="color:{bull_color}">{bull_display}</div>
                    <div class="driver-list-sober">
                        • <b>WACC:</b> {bull_wacc*100:.2f}% (Eficiencia ↓)<br>
                        • <b>Crec. 1-5Y:</b> {bull_g1*100:.1f}%<br>
                        • <b>G. Terminal:</b> {bull_gt*100:.1f}%<br>
                        • <b>Impacto Macro:</b> {bull_macro*100:.1f}%
                    </div>
                </div>""", unsafe_allow_html=True)
                if bull_display == "N/A":
                    st.warning("⚠️ El escenario **Bull** no converge (WACC 3.5% vs G 4.0%). Sube el WACC base para habilitar.")

            # --- BRIDGE WATERFALL (CALIBRACIÓN DE ESCALA $B) ---
            st.markdown("---")
            
            # 1. Definimos la Caja Neta en Billones
            net_cash_b = data.get('cash_b', 0) - data.get('debt_b', 0)
            
            # 2. El Total (Equity Value) debe estar en Billones
            equity_val_b = (v_base * data.get('shares_m', 443.6)) / 1000 
            
            fig_water = go.Figure(go.Waterfall(
                orientation="v", 
                measure=["relative", "relative", "relative", "total"],
                x=["PV Flujos 10Y", "Valor Terminal", "Caja Neta", "Market Cap Est. ($B)"],
                y=[pv_f, pv_t, net_cash_b, equity_val_b],
                text=[f"${pv_f:.1f}B", f"${pv_t:.1f}B", f"${net_cash_b:.1f}B", f"${equity_val_b:.1f}B"],
                textposition="outside", 
                connector={"line":{"color":"rgba(255,255,255,0.1)"}},
                decreasing={"marker":{"color":"#f85149"}},
                increasing={"marker":{"color":"#3fb950"}},
                totals={"marker":{"color":"#005BAA"}}
            ))
            
            fig_water.update_layout(
                title="Desglose del Valor de Mercado Proyectado ($B)", 
                template="plotly_dark", height=450,
                yaxis_title="Billones USD",
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_water, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 2: SCORECARD & RADAR (RESTAURADO)
    # -------------------------------------------------------------------------
    with tabs[1]:
        st.subheader("Tablero de Salud Fundamental e Inteligencia")
        col_diag1, col_diag2 = st.columns([1.5, 1])
        with col_diag1:
            inf_data = data['acc_summary']
            diagnostics = [
                (f"Margen Operativo líder sectorial: {inf_data['Operating Margin (%)']:.2f}%", True, "star"),
                (f"Consenso de {data['analysts']['count']} Analistas: {data['analysts']['key']}", True, "star"),
                ("Múltiplo P/E premium vs Media Retail (Costo de Calidad)", True, "alert"),
                ("Retención de membresía estable >90% (Audit 10-K)", True, "star"),
                ("Retorno sobre Capital (ROE) superior al 25% anual", True, "star")
            ]
            for text, cond, i_type in diagnostics:
                color = "var(--success-green)" if i_type == "star" else "var(--accent-gold)"
                st.markdown(f'<div class="conclusion-item"><div class="icon-box" style="color:{color}">{"✪" if i_type=="star" else "!"}</div><div class="text-box">{text}</div></div>', unsafe_allow_html=True)
        
        with col_diag2:
            radar_vals = [4.8, 5, 4.5, 4.2, 2.5] 
            fig_radar = px.line_polar(r=radar_vals, theta=['Salud', 'Ganancias', 'Crecimiento', 'Foso', 'Precio'], line_close=True, range_r=[0,5])
            fig_radar.update_traces(fill='toself', line_color='#005BAA', opacity=0.8)
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=False)), height=450, template="plotly_dark")
            st.plotly_chart(fig_radar, use_container_width=True)

# -------------------------------------------------------------------------
    # TAB 2: PEER ANALYSIS & MARKET BENCHMARKING (TOTALMENTE INTERACTIVO)
    # -------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("🔬 Peer Analysis & Market Benchmarking (Real-Time)")
        
        # 1. Mapeo de nombres legibles a Tickers de Yahoo Finance
        market_map = {
            "S&P 500 (Market)": "SPY",
            "Nasdaq 100 (Tech)": "QQQ",
            "Walmart (WMT)": "WMT",
            "Target (TGT)": "TGT",
            "BJ's Wholesale (BJ)": "BJ",
            "Kroger (KR)": "KR",
            "Amazon (AMZN)": "AMZN",
            "Home Depot (HD)": "HD",
            "Lowe's (LOW)": "LOW",
            "Sprouts (SFM)": "SFM",
            "Dollar Tree (DLTR)": "DLTR",
            "Dollar General (DG)": "DG"
        }

        # 2. Selector On-Demand (Incluyendo Índices)
        selected_labels = st.multiselect(
            "Selecciona activos y benchmarks para el análisis comparativo:",
            options=list(market_map.keys()),
            default=["S&P 500 (Market)", "Nasdaq 100 (Tech)", "Walmart (WMT)", "Target (TGT)", "Amazon (AMZN)", "BJ's Wholesale (BJ)"],
            help="Puedes agregar índices de mercado o competidores específicos para recalcular la terminal."
        )

        # Traducimos etiquetas a tickers para la API, siempre incluyendo a COST
        selected_tickers = [market_map[label] for label in selected_labels]
        full_ticker_list = ["COST"] + selected_tickers

        with st.spinner("Sincronizando terminal con Wall Street..."):
            # Descarga de métricas fundamentales
            df_full_comparison = InstitutionalDataService.fetch_peer_group_data(full_ticker_list)
            
# --- BLOQUE DE SEGURIDAD PARA MODO BÚNKER ---
        # Definimos un diccionario de respaldo (bunker_names) para asegurar que reverse_map siempre exista
        bunker_names = {
            "COST": "Costco", "WMT": "Walmart", "TGT": "Target", 
            "BJ": "BJ's", "KR": "Kroger", "AMZN": "Amazon", 
            "HD": "Home Depot", "LOW": "Lowe's", "SFM": "Sprouts", 
            "DLTR": "Dollar Tree", "DG": "Dollar General", 
            "SPY": "S&P 500", "QQQ": "Nasdaq 100"
        }

        # --- NORMALIZACIÓN DE DATOS COMPARATIVOS ---
        if df_full_comparison is not None and not df_full_comparison.empty:
            # 1. Limpieza de Duplicados (Evita las barras dobles de COST)
            df_full_comparison = df_full_comparison.drop_duplicates(subset=['Ticker'])
            
            # 2. Mapeo de Nombres (Prioriza nombres reales, usa Ticker como respaldo)
            # Intentamos usar el market_map o el bunker_names, si no, dejamos el Ticker
            all_names = {**bunker_names, **{v: k.split(" (")[0] for k, v in market_map.items()}}
            df_full_comparison['Nombre'] = df_full_comparison['Ticker'].map(all_names).fillna(df_full_comparison['Ticker'])
            
            # 3. Asegurar que COST esté presente para el análisis de Valoración
            if "COST" not in df_full_comparison['Ticker'].values:
                cost_row = pd.DataFrame([{
                    "Ticker": "COST", "Nombre": "Costco Wholesale",
                    "Mkt Cap ($B)": payload.get('mkt_cap_b', 450),
                    "P/E Ratio": payload['info'].get('trailingPE', 53.0),
                    "ROE (%)": payload['acc_summary'].get('ROE (%)', 30.0),
                    "EV/EBITDA": 33.0
                }])
                df_full_comparison = pd.concat([df_full_comparison, cost_row], ignore_index=True)
        else:
            # Fallback total si no hay NADA de datos
            st.warning("⚠️ Terminal en modo de emergencia: Sin datos comparativos disponibles.")
            df_full_comparison = pd.DataFrame(columns=['Ticker', 'Nombre', 'Mkt Cap ($B)', 'P/E Ratio', 'ROE (%)', 'EV/EBITDA'])
        # --------------------------------------------

# --- VISUALIZACIÓN 1: RENDIMIENTO RELATIVO DINÁMICO (UNIVERSO EXTENDIDO) ---
        st.write(f"**Rendimiento Normalizado 1Y: COST vs Ecosistema de Retail & Mercado**")
        
        archivo_historia = "market_history.csv"
        perf_df = None

        # Definimos el mapeo institucional completo
        nombres_pro = {
            "COST": "Costco (COST)",
            "SPY": "S&P 500 (Market)",
            "QQQ": "Nasdaq 100 (Tech)",
            "WMT": "Walmart (WMT)",
            "TGT": "Target (TGT)",
            "BJ": "BJ's Wholesale (BJ)",
            "KR": "Kroger (KR)",
            "AMZN": "Amazon (AMZN)",
            "HD": "Home Depot (HD)",
            "LOW": "Lowe's (LOW)",
            "SFM": "Sprouts (SFM)",
            "DLTR": "Dollar Tree (DLTR)",
            "DG": "Dollar General (DG)"
        }

        try:
            # 1. INTENTO ONLINE: Descarga del universo completo
            tickers_universo = list(nombres_pro.keys())
            with st.spinner("Sincronizando universo de inversión..."):
                perf_df = yf.download(tickers_universo, period="1y", progress=False)['Close']
            
            if perf_df is None or perf_df.empty:
                raise ValueError("API Yahoo Offline")
                
        except Exception:
            # 2. FALLBACK OFFLINE: Rescate desde el Búnker market_history.csv
            if os.path.exists(archivo_historia):
                perf_df = pd.read_csv(archivo_historia, index_col=0, parse_dates=True)
                st.sidebar.info("🏛️ Universo extendido cargado desde el Búnker Local.")
            else:
                st.info("📉 Nota: Modo offline activo. Cargue 'market_history.csv' para ver comparativas.")

        # --- RENDERIZADO DEL GRÁFICO DE RENDIMIENTO ---
        if perf_df is not None and not perf_df.empty:
            # Normalización Base 100
            perf_norm = (perf_df / perf_df.iloc[0]) * 100
            
            # Limpiamos columnas: solo dejamos las que están en nuestro mapeo y existen en el DF
            columnas_finales = [c for c in perf_norm.columns if c in nombres_pro]
            perf_norm = perf_norm[columnas_finales]
            
            # Renombramos columnas para la leyenda profesional
            perf_norm.columns = [nombres_pro.get(col, col) for col in perf_norm.columns]
            
            fig_perf = px.line(perf_norm, template="plotly_dark")
            
            # Destacamos a COST con una línea más gruesa
            if "Costco (COST)" in perf_norm.columns:
                fig_perf.update_traces(selector=dict(name="Costco (COST)"), line=dict(width=4, color="#005BAA"))
            
            fig_perf.update_layout(
                height=550, 
                hovermode="x unified", 
                yaxis_title="Rendimiento (Base 100)",
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=-0.5, 
                    xanchor="center", 
                    x=0.5
                )
            )
            st.plotly_chart(fig_perf, use_container_width=True)
            
        # --- VISUALIZACIÓN 2: DISPERSIÓN DE VALORACIÓN ---
        c_p1, c_p2 = st.columns(2)
        
        with c_p1:
            # --- BLOQUE DE SEGURIDAD PARA GRÁFICO DE DISPERSIÓN ---
            st.write(f"**Análisis de Valoración Relativa: P/E vs ROE**")
            
            # 1. Verificamos que el DataFrame exista y no esté vacío
            if df_full_comparison is not None and not df_full_comparison.empty:
                # 2. LIMPIEZA PARA GRÁFICO: Excluimos índices para no distorsionar escalas
                df_fundamentales = df_full_comparison[~df_full_comparison['Ticker'].isin(['SPY', 'QQQ', '^GSPC', '^IXIC'])]
                
                cols_grafico = ["P/E Ratio", "ROE (%)", "Mkt Cap ($B)"]
                columnas_presentes = [c for c in cols_grafico if c in df_fundamentales.columns]
                
                if len(columnas_presentes) == len(cols_grafico):
                    df_plot_scat = df_fundamentales.dropna(subset=cols_grafico)
                    
                    if not df_plot_scat.empty:
                        try:
                            fig_scat = px.scatter(
                                df_plot_scat, 
                                x="P/E Ratio", 
                                y="ROE (%)",
                                size="Mkt Cap ($B)", 
                                color="Nombre", 
                                text="Ticker",
                                template="plotly_dark", 
                                size_max=40
                            )
                            fig_scat.update_layout(height=450)
                            st.plotly_chart(fig_scat, use_container_width=True)
                        except Exception:
                            st.info("📊 Error al generar gráfico de dispersión.")
                    else:
                        st.warning("⚠️ Datos insuficientes para dispersión (Modo Búnker).")
                else:
                    st.info("📊 Columnas de análisis no encontradas.")
            else:
                st.info("📊 Esperando datos de competidores...")

        with c_p2:
            st.write("**Eficiencia Operativa: Margen Neto**")
            try:
                # 1. Carga de datos
                df_ef = pd.read_csv("peers_stats.csv") if os.path.exists("peers_stats.csv") else df_full_comparison
                
                # 2. LIMPIEZA FORZADA (Basado en tu imagen de Excel)
                # Buscamos la columna 'Net Margin (%)'
                target_col = "Net Margin (%)"
                
                if target_col in df_ef.columns:
                    # Convertimos a número quitando cualquier cosa que no sea dígito o punto
                    df_ef[target_col] = pd.to_numeric(
                        df_ef[target_col].astype(str).str.replace(r'[^0-9.]', '', regex=True), 
                        errors='coerce'
                    )
                    
                    # 3. Filtrado de activos (Quitamos Benchmarks)
                    df_plt = df_ef[~df_ef['Ticker'].isin(['SPY', 'QQQ', '^GSPC', '^IXIC'])].copy()
                    df_plt = df_plt.dropna(subset=[target_col])
                    df_plt = df_plt[df_plt[target_col] > 0].sort_values(target_col)

                    if not df_plt.empty:
                        # Color: Costco Azul, el resto Gris
                        colors = ["#005BAA" if str(t).upper() == "COST" else "#444444" for t in df_plt['Ticker']]
                        
                        fig_m = px.bar(
                            df_plt, x="Ticker", y=target_col,
                            text_auto='.2f',
                            template="plotly_dark",
                            title="Métrica: Margen Neto (%)"
                        )
                        
                        fig_m.update_traces(
                            marker_color=colors, 
                            textposition='outside',
                            textsuffix='%'
                        )
                        
                        fig_m.update_layout(
                            height=400, 
                            showlegend=False, 
                            margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title="Margen Neto (%)"
                        )
                        
                        st.plotly_chart(fig_m, use_container_width=True)
                    else:
                        st.warning("⚠️ Los valores de margen parecen ser cero o inválidos.")
                else:
                    # Si por alguna razón el nombre cambió ligeramente
                    st.info(f"📊 Buscando columna '{target_col}'... No detectada. Columnas actuales: {list(df_ef.columns)}")

            except Exception as e:
                st.error(f"Error técnico: {e}")
                
# --- SECCIÓN: MATRIZ DE CORRELACIÓN (COSTCO FIRST + SYMBOLS FIX) ---
        st.markdown("---")
        st.write("**🧩 Matriz de Correlación de Retornos Diarios (1Y)**")
        with st.expander("Ver Análisis de Correlación"):
            # Verificamos si perf_df tiene datos
            if 'perf_df' in locals() and perf_df is not None and not perf_df.empty:
                try:
                    # 1. Calculamos retornos y renombramos índices de mercado a símbolos de ETF
                    # Aseguramos que el mapeo use SPY y QQQ para los nombres
                    nombres_pro_corr = nombres_pro.copy()
                    nombres_pro_corr.update({"^GSPC": "S&P 500 (SPY)", "^IXIC": "Nasdaq 100 (QQQ)"})
                    
                    returns_df = perf_df.pct_change().dropna()
                    
                    # 2. Renombrar columnas ANTES de calcular la correlación
                    returns_df.columns = [nombres_pro_corr.get(col, col) for col in returns_df.columns]
                    corr_matrix = returns_df.corr()

                    # 3. ORDENAMIENTO PERSONALIZADO: Costco (COST) siempre primero
                    # Buscamos el nombre exacto que tiene Costco en el mapeo
                    costco_label = nombres_pro.get("COST", "Costco (COST)")
                    
                    if costco_label in corr_matrix.columns:
                        # Reordenamos las columnas y filas para que Costco sea el índice 0
                        cols = [costco_label] + [c for c in corr_matrix.columns if c != costco_label]
                        corr_matrix = corr_matrix.reindex(index=cols, columns=cols)
                    
                    # 4. RENDERIZADO DEL HEATMAP
                    fig_corr = px.imshow(
                        corr_matrix, 
                        text_auto=".2f", 
                        color_continuous_scale='RdBu_r', # Rojo (Correlación +) vs Azul (Correlación -)
                        zmin=-1, zmax=1, # Escala fija de correlación
                        template="plotly_dark", 
                        aspect="auto"
                    )
                    
                    fig_corr.update_layout(
                        height=600,
                        margin=dict(l=20, r=20, t=20, b=20)
                    )
                    
                    st.plotly_chart(fig_corr, use_container_width=True)
                    
                except Exception as e:
                    st.info(f"📈 No se pudo calcular la correlación: {e}")
            else:
                st.info("📉 Matriz de correlación requiere carga de historial (market_history.csv).")
# --- TABLA MAESTRA CON FORMATO BLOOMBERG (VERSIÓN FINAL BLINDADA) ---
        st.markdown("---")
        st.write("**Matriz Competitiva y de Benchmarks (Sync 2026)**")
        
        if df_full_comparison is not None and not df_full_comparison.empty:
            try:
                # 1. LIMPIEZA Y NORMALIZACIÓN DE DATOS
                df_master = df_full_comparison.copy()
                
                # --- CORRECCIÓN DE DIVIDEND YIELD (Target y otros) ---
                # Si el yield es > 20%, asumimos error de escala y dividimos por 100
                if 'Div Yield (%)' in df_master.columns:
                    df_master['Div Yield (%)'] = df_master['Div Yield (%)'].apply(
                        lambda x: x/100 if x > 20 else x
                    )
                    # Corrección específica manual para Target si persiste el error
                    df_master.loc[df_master['Ticker'] == 'TGT', 'Div Yield (%)'] = 2.95

                # 2. ASEGURAR UNIVERSO COMPLETO (Si faltan empresas del CSV)
                # Si por alguna razón el filtrado previo quitó empresas, aquí las recuperamos
                # (Asegúrate de que df_full_comparison no haya sido filtrado antes de este bloque)

                # 3. ORDENAMIENTO PRIORITARIO: COSTCO SIEMPRE ARRIBA
                df_master['Priority'] = df_master['Ticker'].apply(lambda x: 0 if x == 'COST' else 1)
                df_master = df_master.sort_values(['Priority', 'Mkt Cap ($B)'], ascending=[True, False]).drop('Priority', axis=1)

                # 4. DEFINICIÓN DE FORMATOS
                cols_formato = {
                    "Mkt Cap ($B)": "{:.1f}",
                    "P/E Ratio": "{:.2f}",
                    "EV/EBITDA": "{:.2f}",
                    "EV/FCF": "{:.2f}",
                    "ROE (%)": "{:.1f}%",
                    "Net Margin (%)": "{:.2f}%",
                    "Rev Growth (%)": "{:.2f}%",
                    "Div Yield (%)": "{:.2f}%" 
                }
                
                columnas_presentes = [c for c in cols_formato.keys() if c in df_master.columns]
                
                # 5. RENDERIZADO CON MAPA DE CALOR INSTITUCIONAL
                st.dataframe(
                    df_master.set_index("Ticker").style.format({c: cols_formato[c] for c in columnas_presentes})
                    # Gradiente VERDE: Rentabilidad y Dividendos
                    .background_gradient(
                        cmap='RdYlGn', 
                        subset=[c for c in ['ROE (%)', 'Net Margin (%)', 'Div Yield (%)'] if c in df_master.columns]
                    )
                    # Gradiente ROJO INVERSO: Valoración (P/E y EV/EBITDA)
                    .background_gradient(
                        cmap='RdYlGn_r', 
                        subset=[c for c in ['P/E Ratio', 'EV/EBITDA'] if c in df_master.columns]
                    )
                    # Gradiente AZUL: Market Cap
                    .background_gradient(
                        cmap='Blues', 
                        subset=[c for c in ['Mkt Cap ($B)'] if c in df_master.columns]
                    ),
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error en matriz: {e}")
                st.dataframe(df_full_comparison, use_container_width=True)
        else:
            st.info("📊 La tabla maestra se poblará al sincronizar con el Búnker de datos.")

        st.caption("Nota: Costco (COST) fijado en cabecera. Datos de Yield normalizados para Target (TGT) y pares.")
        
# -------------------------------------------------------------------------
    # TAB 4: GANANCIAS & SENTIMIENTO (VERSIÓN THEME-AWARE PIXEL-PERFECT)
    # -------------------------------------------------------------------------
    with tabs[3]:
        st.subheader("Análisis de Sentimiento y Proyecciones de Wall Street")
        r_col1, r_col2 = st.columns([1.3, 2])
        
        with r_col1:
            # 1. Extracción de Datos de Consenso
            score_val = data.get('analysts', {}).get('score', 2.0)
            target_val = data.get('analysts', {}).get('target', 1067.59)
            rec_str = data.get('analysts', {}).get('key', 'BUY')
            count_val = data.get('analysts', {}).get('count', 37)
            
            # 2. CSS DINÁMICO (Corrección para Modo Oscuro/Claro)
            st.markdown(f"""
                <style>
                .st-widget-box-dynamic {{
                    background-color: var(--secondary-background-color); 
                    border: 1px solid var(--border-color);
                    border-radius: 12px;
                    padding: 20px;
                    font-family: 'Segoe UI', sans-serif;
                    color: var(--text-color);
                    margin-bottom: 20px;
                }}
                .st-rec-header-dynamic {{ 
                    text-align: center; 
                    border-bottom: 2px solid var(--primary-color); 
                    padding-bottom: 15px; 
                }}
                .st-rec-val-dynamic {{ 
                    font-size: 2.2rem; 
                    font-weight: 900; 
                    color: #1a7f37; /* El verde se mantiene por semántica financiera */
                    margin: 5px 0; 
                }}
                
                .st-data-row-dynamic {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin: 10px 0;
                    height: 25px;
                }}
                .st-data-label-dynamic {{ 
                    width: 125px; 
                    font-size: 0.9rem; 
                    color: var(--text-color); 
                    font-weight: 700; 
                }}
                .st-data-bar-bg-dynamic {{
                    flex-grow: 1;
                    height: 10px;
                    background: var(--background-color);
                    margin: 0 12px;
                    border-radius: 5px;
                    border: 1px solid var(--border-color);
                    overflow: hidden;
                }}
                .st-data-bar-fill-dynamic {{ height: 100%; border-radius: 4px; }}
                
                .st-data-info-dynamic {{ 
                    width: 105px; 
                    text-align: right; 
                    font-family: 'JetBrains Mono', monospace; 
                    font-size: 0.85rem; 
                    font-weight: 800;
                    color: var(--text-color); 
                }}
                .st-data-footer-dynamic {{ 
                    border-top: 2px solid var(--border-color); 
                    margin-top: 15px; 
                    padding-top: 15px; 
                }}
                .st-footer-line-dynamic {{ 
                    display: flex; 
                    justify-content: space-between; 
                    margin-bottom: 8px; 
                    font-size: 0.9rem; 
                }}
                .st-footer-label-dynamic {{ color: var(--text-color); opacity: 0.8; font-weight: 600; }}
                .st-footer-val-dynamic {{ color: var(--text-color); font-weight: 800; }}
                </style>
                
                <div class="st-widget-box-dynamic">
                    <div class="st-rec-header-dynamic">
                        <div style="font-size: 0.8rem; text-transform: uppercase; font-weight: 800; letter-spacing: 1px; opacity: 0.9;">Recomendación de los analistas</div>
                        <div class="st-rec-val-dynamic">{rec_str.title()}</div>
                        <div style="font-size: 0.75rem; opacity: 0.8; font-weight: 600;">Basado en {count_val} analistas, {datetime.date.today().strftime('%d/%m/%Y')}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # 3. Gráfico Gauge (Inversión 6 - score_val)
            gauge_pos = 6 - score_val
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge", value = gauge_pos,
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [1, 5], 'visible': False},
                    'bar': {'color': "var(--primary-color)", 'thickness': 0.08},
                    'steps': [
                        {'range': [1, 1.8], 'color': '#d73a49'},
                        {'range': [1.8, 2.6], 'color': '#fb8f44'},
                        {'range': [2.6, 3.4], 'color': '#f6e05e'},
                        {'range': [3.4, 4.2], 'color': '#2da44e'},
                        {'range': [4.2, 5], 'color': '#1a7f37'}
                    ],
                    'threshold': {'line': {'color': "var(--text-color)", 'width': 3}, 'thickness': 0.8, 'value': gauge_pos}
                }
            ))
            fig_gauge.update_layout(height=160, margin=dict(t=10, b=0, l=30, r=30), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

            # 4. Distribución Detallada (Las 5 filas originales)
            st.markdown(f"""
                <div class="st-widget-box-dynamic" style="background: transparent; padding-top: 0; margin-top: -30px; border: none; box-shadow: none;">
                    <div class="st-data-row-dynamic">
                        <div class="st-data-label-dynamic">Compra agresiva</div>
                        <div class="st-data-bar-bg-dynamic"><div class="st-data-bar-fill-dynamic" style="width: 54%; background: #1a7f37;"></div></div>
                        <div class="st-data-info-dynamic">20 (54.1%)</div>
                    </div>
                    <div class="st-data-row-dynamic">
                        <div class="st-data-label-dynamic">Comprar</div>
                        <div class="st-data-bar-bg-dynamic"><div class="st-data-bar-fill-dynamic" style="width: 8%; background: #2da44e;"></div></div>
                        <div class="st-data-info-dynamic">3 (8.1%)</div>
                    </div>
                    <div class="st-data-row-dynamic">
                        <div class="st-data-label-dynamic">Conservar</div>
                        <div class="st-data-bar-bg-dynamic"><div class="st-data-bar-fill-dynamic" style="width: 32%; background: #f6e05e;"></div></div>
                        <div class="st-data-info-dynamic">12 (32.4%)</div>
                    </div>
                    <div class="st-data-row-dynamic">
                        <div class="st-data-label-dynamic">Vender</div>
                        <div class="st-data-bar-bg-dynamic"><div class="st-data-bar-fill-dynamic" style="width: 0%; background: #fb8f44;"></div></div>
                        <div class="st-data-info-dynamic">0 (0.0%)</div>
                    </div>
                    <div class="st-data-row-dynamic">
                        <div class="st-data-label-dynamic">Venta fuerte</div>
                        <div class="st-data-bar-bg-dynamic"><div class="st-data-bar-fill-dynamic" style="width: 5%; background: #d73a49;"></div></div>
                        <div class="st-data-info-dynamic">2 (5.4%)</div>
                    </div>
                    <div class="st-data-footer-dynamic">
                        <div class="st-footer-line-dynamic">
                            <span class="st-footer-label-dynamic">Precio previsto (12m)</span>
                            <span class="st-footer-val-dynamic">USD {target_val:,.2f}</span>
                        </div>
                        <div class="st-footer-line-dynamic">
                            <span class="st-footer-label-dynamic">Volatilidad</span>
                            <span class="st-footer-val-dynamic">Promedio</span>
                        </div>
                        <div class="st-footer-line-dynamic">
                            <span class="st-footer-label-dynamic">Recomendación sector</span>
                            <span class="st-footer-val-dynamic" style="color:#1a7f37;">Comprar</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with r_col2:
            # 5. Gráfico de Ganancias Pro (BPA)
            quarters = ['2025Q3', '2025Q4', '2026Q1', '2026Q2']
            fig_eps = go.Figure()
            fig_eps.add_trace(go.Bar(x=quarters, y=[3.80, 5.51, 4.55, 4.55], name="Estimado", marker_color="#495057"))
            fig_eps.add_trace(go.Bar(x=quarters, y=[3.92, 5.82, 4.58, 4.58], name="Real", marker_color="#005BAA"))
            
            fig_eps.update_layout(
                title="Sorpresas en Beneficio por Acción (BPA)",
                barmode='group',
                template="plotly_dark", 
                height=480,
                xaxis_type='category',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_eps, use_container_width=True)
            
# -------------------------------------------------------------------------
    # TAB 5: STRESS TEST PRO (VERSIÓN FINAL SIN ERRORES)
    # -------------------------------------------------------------------------
    with tabs[4]:
        st.subheader("🌪️ Simulador de Cisnes Negros & Shocks de Mercado")
        st.markdown("""<div style="background-color:rgba(248, 81, 73, 0.1); padding:15px; border-radius:10px; border-left: 5px solid #f85149; margin-bottom:20px;">
            <b>Protocolo de Stress Test:</b> Estos escenarios simulan eventos de baja probabilidad pero alto impacto (Fat Tails). 
            Los ajustes se suman al entorno macroeconómico actual.</div>""", unsafe_allow_html=True)
        
        # 1. Configuración del Entorno de Crisis (Local)
        col_s1, col_s2 = st.columns(2)
        s_income_local = col_s1.slider("Shock: Consumo Disponible (%)", -30.0, 5.0, -10.0) / 100
        s_infl_local = col_s2.slider("Shock: Inflación de Costos (%)", 0.0, 25.0, 10.0) / 100
        
        st.markdown("### 🛠️ Selección de Eventos de Riesgo")
        
        # Creamos las columnas para los checkboxes
        c_sw1, c_sw2, c_sw3, c_sw4 = st.columns(4)
        
        # Inicializamos acumuladores
        impact_fcf = 0.0
        impact_wacc = 0.0
        impact_g = 0.0
        active_risks = []

        # --- DISEÑO DE COLUMNAS CON IMPACTOS VISIBLES ---
        with c_sw1:
            check_ciber = st.checkbox("Ataque Cibernético")
            st.markdown("<small style='color:#808495;'>📉 FCF: <b>-15%</b><br>⚖️ WACC: <b>+0 bps</b><br>📈 g: <b>0%</b></small>", unsafe_allow_html=True)
            if check_ciber:
                impact_fcf -= 0.15
                active_risks.append("💻 <b>Ciber-Riesgo:</b> Interrupción Operativa Grave")

        with c_sw2:
            check_lock = st.checkbox("Lockdown Global")
            st.markdown("<small style='color:#808495;'>📉 FCF: <b>-25%</b><br>⚖️ WACC: <b>+100 bps</b><br>📈 g: <b>0%</b></small>", unsafe_allow_html=True)
            if check_lock:
                impact_fcf -= 0.25; impact_wacc += 0.01
                active_risks.append("🔒 <b>Lockdown:</b> Parálisis logística y de suministros")

        with c_sw3:
            check_geo = st.checkbox("Conflicto Geopolítico")
            st.markdown("<small style='color:#808495;'>📉 FCF: <b>-10%</b><br>⚖️ WACC: <b>+250 bps</b><br>📈 g: <b>-1.0%</b></small>", unsafe_allow_html=True)
            if check_geo:
                impact_fcf -= 0.10; impact_wacc += 0.025; impact_g -= 0.01
                active_risks.append("🌍 <b>Geopolítica:</b> Inestabilidad y riesgo país elevado")

        with c_sw4:
            check_mem = st.checkbox("Crisis de Membresías")
            st.markdown("<small style='color:#808495;'>📉 FCF: <b>-20%</b><br>⚖️ WACC: <b>+0 bps</b><br>📈 g: <b>-2.0%</b></small>", unsafe_allow_html=True)
            if check_mem:
                impact_fcf -= 0.20; impact_g -= 0.02
                active_risks.append("💳 <b>Membresías:</b> Pérdida de recurrencia y churn masivo")

        # 2. Consolidación de Variables Post-Stress
        total_macro_stress = (s_income_local * 1.5) - (s_infl_local * 1.2) + impact_fcf
        stress_wacc = final_wacc + impact_wacc
        stress_g1 = g1_in + impact_g
        
        # 3. Cálculo de Valoración bajo Estrés
        v_stress, _, _, _ = ValuationOracle.run_macro_dcf(
            data['fcf_now_b'], stress_g1, g2_in, stress_wacc, g_terminal,
            shares=data['shares_m'], cash=data['cash_b'], debt=data['debt_b'], macro_adj=total_macro_stress
        )

        # 4. Panel de Resultados (CORREGIDO PARA EVITAR DELTAGENERATOR)
        st.markdown("---")
        res_col1, res_col2 = st.columns([1, 2])
        
        with res_col1:
            diff_pct = (v_stress / f_val - 1) * 100
            st.metric("Fair Value en Crisis", f"${v_stress:.2f}", f"{diff_pct:.1f}% vs Base", delta_color="inverse")
            
            # Determinamos el nivel de riesgo
            risk_level = "CRÍTICO" if diff_pct < -30 else ("ALTO" if diff_pct < -15 else "MODERADO")
            
            # Usamos un bloque if/else estándar para que Streamlit no imprima el objeto devuelto
            if diff_pct < -15:
                st.error(f"Riesgo de la acción: **{risk_level}**")
            else:
                st.success(f"Riesgo: **{risk_level}**")

        with res_col2:
            st.write("**Resumen de Drivers Resultantes:**")
            d1, d2, d3 = st.columns(3)
            d1.metric("WACC Stress", f"{stress_wacc*100:.2f}%", f"+{impact_wacc*10000:.0f} bps")
            d2.metric("Growth Stress", f"{stress_g1*100:.1f}%", f"{impact_g*100:.1f}%")
            d3.metric("FCF Adjustment", f"{total_macro_stress*100:.1f}%", "Impacto Neto")

# -------------------------------------------------------------------------
    # TAB 6: FORWARD LOOKING (VARIABLES AJUSTABLES)
    # -------------------------------------------------------------------------
    with tabs[5]:
        st.subheader("Laboratorio de Resultados Proyectados (Forward Looking)")
        f1, f2, f3, f4 = st.columns(4)
        rf_g = f1.slider("Crec. Ventas (%)", 0.0, 25.0, 8.5) / 100
        mf_e = f2.slider("Margen EBITDA (%)", 3.0, 15.0, 5.2) / 100
        re_f = f3.slider("Capex/Sales (%)", 1.0, 8.0, 2.0) / 100
        tax_f = f4.slider("Tax Rate (%)", 15.0, 35.0, 21.0) / 100
        
        yrs = [2026, 2027, 2028, 2029, 2030]
        p_revs = [data['acc_summary']['Revenue ($B)'] * (1 + rf_g)**i for i in range(1, 6)]
        
        # 1. Creamos el DataFrame
        df_fwd = pd.DataFrame({
            "Año": yrs, 
            "Rev ($B)": p_revs, 
            "EBITDA ($B)": [r * mf_e for r in p_revs]
        })

        # 2. TABLA: Convertimos Año a string para que no tenga decimales ni comas
        df_display = df_fwd.copy()
        df_display["Año"] = df_display["Año"].astype(str)
        st.table(df_display.style.format({
            "Rev ($B)": "{:,.2f}", 
            "EBITDA ($B)": "{:,.2f}"
        }))

        # 3. GRÁFICO: Forzamos el eje X a ser discreto y sin formato decimal
        fig_fwd = px.line(df_fwd, x="Año", y="Rev ($B)", markers=True, title="Trayectoria Proyectada de Ingresos")
        fig_fwd.update_layout(
            xaxis=dict(
                tickmode='linear',
                dtick=1,        # Salto de 1 en 1
                tickformat='d'  # 'd' de dígito entero (sin comas ni decimales)
            ),
            yaxis_tickformat="$,.0f", # Aprovechamos para poner comas y $ en el eje Y
            template="plotly_dark"
        )
        st.plotly_chart(fig_fwd, use_container_width=True)
        
# -------------------------------------------------------------------------
    # TAB 7: FINANZAS & RATIOS PRO (BLOOMBERG TERMINAL INTEGRATED - ANTI-CRASH)
    # -------------------------------------------------------------------------
    with tabs[6]:
        st.subheader("🏛️ Terminal de Inteligencia Financiera: Costco Wholesale")
        st.info("Fusión de Estados Financieros de Gestión y Ratios de Eficiencia Operativa (2022-2025).")
        
        # 1. Extracción y Limpieza de Datos (IS, BS, CF)
        is_raw = data['is'].copy()
        bs_raw = data['bs'].copy()
        cf_raw = data['cf'].copy()

        # Función para asegurar orden cronológico y quitar 2021
        def prepare_financials(df):
            df = df[df.columns[::-1]] # Antiguo -> Reciente
            valid_cols = [c for c in df.columns if str(c).split('-')[0] != '2021']
            return df[valid_cols]

        is_f = prepare_financials(is_raw)
        bs_f = prepare_financials(bs_raw)
        cf_f = prepare_financials(cf_raw)
        
        # Variable unificada para los años (eje X)
        años_finales = [str(c).split('-')[0] for c in is_f.columns]

        # 2. SISTEMA DE EXTRACCIÓN ROBUSTA (Helper para evitar KeyErrors)
        def safe_get(df, keys):
            for k in keys:
                if k in df.index:
                    return df.loc[k]
            # Si no encuentra nada, devolvemos una serie de ceros para no romper el cálculo
            return pd.Series(0, index=df.columns)

        # 3. CÁLCULO DE RATIOS PRO CON FALLBACKS
        try:
            # Definición de lineas con sus alias comunes en yfinance
            net_income = safe_get(is_f, ['Net Income Common Stockholders', 'Net Income', 'Net Income From Continuing Operation Net Minority Interest'])
            total_equity = safe_get(bs_f, ['Stockholders Equity', 'Total Stockholders Equity'])
            total_assets = safe_get(bs_f, ['Total Assets'])
            revenue = safe_get(is_f, ['Total Revenue', 'Revenue'])
            cogs = safe_get(is_f, ['Cost Of Revenue'])
            inventory = safe_get(bs_f, ['Inventory'])
            total_debt = safe_get(bs_f, ['Total Debt'])
            ebitda = safe_get(is_f, ['EBITDA'])
            curr_assets = safe_get(bs_f, ['Current Assets', 'Total Current Assets'])
            curr_liab = safe_get(bs_f, ['Current Liabilities', 'Total Current Liabilities'])
            op_inc = safe_get(is_f, ['Operating Income', 'Operating Profit'])
            eps = safe_get(is_f, ['Basic EPS', 'EPS Basic'])

            # Cálculos matemáticos
            roe = (net_income / total_equity) * 100
            roa = (net_income / total_assets) * 100
            asset_turnover = revenue / total_assets
            inv_turnover = cogs / inventory
            debt_ebitda = total_debt / ebitda
            current_ratio = curr_assets / curr_liab
            rev_growth = revenue.pct_change() * 100
            eps_growth = eps.pct_change() * 100

            df_ratios_pro = pd.DataFrame({
                "Crecimiento Ingresos (%)": rev_growth,
                "Crecimiento BPA (%)": eps_growth,
                "ROE (%)": roe,
                "ROA (%)": roa,
                "Rotación Activos (x)": asset_turnover,
                "Rotación Inventario (x)": inv_turnover,
                "Deuda / EBITDA (x)": debt_ebitda,
                "Ratio Liquidez (Current)": current_ratio
            }).T
            df_ratios_pro.columns = años_finales
        except Exception as e:
            st.error(f"Error crítico en el motor de cálculo: {e}")

        # --- SECCIÓN I: ESTADO DE RESULTADOS DE GESTIÓN ---
        st.markdown("### 📊 I. Estado de Resultados de Gestión")
        
        # Mapeo de nombres para la tabla visual
        orden_p_l = [
            (revenue, 'Ingresos Totales'),
            (cogs, 'Coste de Ventas (COGS)'),
            (safe_get(is_f, ['Gross Profit']), 'Utilidad Bruta'),
            (safe_get(is_f, ['Operating Expense']), 'Gastos Operativos (OPEX)'),
            (op_inc, 'Utilidad Operativa (EBIT)'),
            (ebitda, 'EBITDA'),
            (net_income, 'Utilidad Neta'),
            (eps, 'BPA (Beneficio por Acción)')
        ]
        
        # Construcción del DataFrame de visualización
        df_pl_viz = pd.DataFrame([x[0] for x in orden_p_l], index=[x[1] for x in orden_p_l])
        
        # Normalización a Billones (excepto EPS)
        for row in df_pl_viz.index:
            if row != 'BPA (Beneficio por Acción)':
                df_pl_viz.loc[row] = df_pl_viz.loc[row] / 1e9
        
        df_pl_viz.columns = años_finales

        c1, c2 = st.columns([1, 1.2], gap="large")
        with c1:
            st.write("**P&L Institucional ($B)**")
            st.table(df_pl_viz.style.format("{:.2f}"))
        
        with c2:
            st.write("**P&L: Crecimiento vs. Rentabilidad Neta**")
            m_neto = (net_income / revenue) * 100
            
            # CAMBIO 1: Activar el soporte para doble eje
            fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
            
            # CAMBIO 2: Barras (Revenue) al eje principal (False)
            fig_dual.add_trace(go.Bar(
                x=años_finales, 
                y=df_pl_viz.loc['Ingresos Totales'], 
                name="Revenue ($B)", 
                marker_color="#005BAA"
            ), secondary_y=False)
            
            # CAMBIO 3: Línea (Margen) al eje secundario (True)
            fig_dual.add_trace(go.Scatter(
                x=años_finales, 
                y=m_neto.values, 
                name="Margen Neto (%)", 
                line=dict(color="#f85149", width=4), 
                marker=dict(size=10, symbol="diamond")
            ), secondary_y=True)
            
            # CAMBIO 4: Identificación precisa de ejes
            # Configuración Maestra con Propiedades Planas (Anti-Error)
            fig_dual.update_layout(
                template="plotly_dark",
                height=400,
                hovermode="x unified",
                legend=dict(orientation="h", y=1.1, x=1),
                margin=dict(t=30, b=10),
                
                # Configuración Eje X
                xaxis_title="Año",
                xaxis_tickmode="linear",
                xaxis_dtick=1,

                # Configuración Eje Y Primario (Revenue)
                yaxis_title="Revenue ($B)",
                yaxis_tickformat="$,.0f",
                yaxis_side="left",

                # Configuración Eje Y Secundario (Margen)
                yaxis2_title="Net Margin (%)",
                yaxis2_tickformat=".1f",
                yaxis2_ticksuffix="%", 
                yaxis2_side="right",
                yaxis2_overlaying="y",
                yaxis2_showgrid=False
            )

            st.plotly_chart(fig_dual, use_container_width=True)
            
        st.markdown("---")

        # --- SECCIÓN II: RATIOS PRO Y EFICIENCIA ---
        st.markdown("### 📈 II. Análisis de Ratios y Eficiencia Operativa")
        
        c3, c4 = st.columns([1, 1.2], gap="large")
        with c3:
            st.write("**Panel de Ratios (Mapa de Calor Interanual)**")
            st.dataframe(
                df_ratios_pro.style.format("{:.2f}").background_gradient(cmap='RdYlGn', axis=1), 
                use_container_width=True
            )
            
            # Exportación robusta
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_pl_viz.to_excel(writer, sheet_name='P_and_L_Management')
                df_ratios_pro.to_excel(writer, sheet_name='Advanced_Ratios')
                is_raw.to_excel(writer, sheet_name='Audit_IS')
                bs_raw.to_excel(writer, sheet_name='Audit_BS')
            
            st.download_button(
                label="💾 Descargar Suite Financiera Completa", 
                data=output.getvalue(), 
                file_name=f"COST_Pro_Analysis.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )

        with c4:
            st.write("**Estructura Comparativa de Márgenes (%)**")
            
            # Cálculos (Aseguramos que sean listas limpias)
            m_bruto = ((safe_get(is_f, ['Gross Profit']) / revenue) * 100).tolist()
            m_op = ((op_inc / revenue) * 100).tolist()
            m_neto_vals = ((net_income / revenue) * 100).tolist()
            
            fig_marg = go.Figure()
            
            # 1. INYECTAMOS EL TEXTO DIRECTAMENTE EN CADA BARRA
            fig_marg.add_trace(go.Bar(
                x=años_finales, y=m_bruto, name="M. Bruto", 
                marker_color="#27ae60",
                text=[f"{v:.1f}%" for v in m_bruto], # Texto pre-formateado
                textposition='outside'
            ))
            
            fig_marg.add_trace(go.Bar(
                x=años_finales, y=m_op, name="M. Operativo", 
                marker_color="#f1c40f",
                text=[f"{v:.1f}%" for v in m_op],
                textposition='outside'
            ))
            
            fig_marg.add_trace(go.Bar(
                x=años_finales, y=m_neto_vals, name="M. Neto", 
                marker_color="#e74c3c",
                text=[f"{v:.1f}%" for v in m_neto_vals],
                textposition='outside'
            ))
            
            # 2. CONFIGURACIÓN DEL LAYOUT (Usando sintaxis plana para evitar errores)
            fig_marg.update_layout(
                template="plotly_dark", 
                barmode='group', 
                height=400,
                margin=dict(t=50, b=20, l=10, r=10),
                legend=dict(orientation="h", y=1.1, x=1),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                # Forzar el símbolo % en el eje Y
                yaxis_ticksuffix="%",
                yaxis_range=[0, max(m_bruto) * 1.3], # Dar espacio para que no se corten los números
                xaxis_tickmode='linear',
                xaxis_dtick=1
            )
            
            st.plotly_chart(fig_marg, use_container_width=True)
            
    # -------------------------------------------------------------------------
    # TAB 8: DCF LAB PRO (MATRIZ CALIBRADA AL PRECIO ACTUAL)
    # -------------------------------------------------------------------------
    with tabs[7]:
        st.subheader("💎 Laboratorio de Valoración: Sensibilidad de Capital vs. Proyección de Caja")
        
        # Cálculos de base para el laboratorio con rampa de desaceleración
        fcf_premium_lab = data['fcf_now_b'] * 1.15 
        col_mtx, col_flow = st.columns([1.2, 1])
        
        with col_mtx:
            st.write(f"**Matriz de Sensibilidad (Punto Neutro: ${p_ref:,.0f})**")
            
            # Rangos dinámicos para WACC y Crecimiento
            w_rng = np.linspace(final_wacc - 0.01, final_wacc + 0.01, 9)
            g_rng = np.linspace(g_terminal - 0.005, g_terminal + 0.005, 9)
            
            # Ejecución del motor DCF estocástico
            z_mtx = [[float(ValuationOracle.run_macro_dcf(fcf_premium_lab, g1, g2_in, w, g_terminal, macro_adj=macro_adj)[0]) for g1 in g_rng] for w in w_rng]

            fig_giant = go.Figure(data=go.Heatmap(
                z=z_mtx,
                x=[f"{x*100:.1f}%" for x in g_rng],
                y=[f"{x*100:.1f}%" for x in w_rng],
                colorscale='RdYlGn', 
                zmid=p_ref, 
                text=[[f"${v:,.0f}" for v in row] for row in z_mtx],
                texttemplate="%{text}", 
                showscale=True
            ))

            fig_giant.update_layout(
                template="plotly_dark", 
                height=600,
                xaxis_title="Crecimiento (%)",
                yaxis_title="WACC (%)",
                yaxis=dict(autorange='reversed'), 
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_giant, use_container_width=True)

        with col_flow:
            st.write("**Evolución del Flujo de Caja ($B)**")
            # Análisis de convergencia económica
            _, _, _, flows_dcf = ValuationOracle.run_macro_dcf(fcf_premium_lab, g1_in, g2_in, final_wacc, g_terminal, macro_adj=macro_adj)
            
            h_yrs = data['hist_years'][::-1]
            f_yrs = [str(int(h_yrs[-1]) + i) for i in range(1, 11)]
            
            fig_f = go.Figure()
            # Datos históricos de flujo libre de caja
            fig_f.add_trace(go.Scatter(
                x=h_yrs, 
                y=data['fcf_hist_b'].values[:3][::-1], 
                name="Histórico", 
                line=dict(color="#005BAA", width=5)
            ))
            # Proyección estocástica
            fig_f.add_trace(go.Scatter(
                x=[h_yrs[-1]] + f_yrs, 
                y=[data['fcf_hist_b'].values[0]] + list(flows_dcf), 
                name="Proyección", 
                line=dict(color="#f85149", dash='dash', width=4)
            ))
            
            fig_f.update_layout(
                template="plotly_dark", 
                height=600, 
                yaxis=dict(title="FCF ($B)", range=[0, max(flows_dcf)*1.3])
            )
            st.plotly_chart(fig_f, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 9: MONTE CARLO - RECALIBRACIÓN INSTITUCIONAL
    # -------------------------------------------------------------------------
    with tabs[8]:
        st.subheader("🎲 Simulación Estocástica de Valoración (1,000 Escenarios)")
        
        # --- GESTIÓN DE SEMILLA DINÁMICA ---
        if 'mc_seed_tab8' not in st.session_state:
            st.session_state['mc_seed_tab8'] = 42

        c_header1, c_header2 = st.columns([3, 1])
        with c_header1:
            st.markdown("""
            Esta simulación recalibra el motor para un **Target Institucional**. 
            Varía aleatoriamente el WACC (entorno al 7.0%) y el Crecimiento (entorno al 11.5%).
            """)
        with c_header2:
            if st.button("🎲 Re-simular"):
                st.session_state['mc_seed_tab8'] = np.random.randint(0, 99999)
        
        # Aplicar la semilla de la sesión
        np.random.seed(st.session_state['mc_seed_tab8'])
        
        n_sims = 1000
        precio_actual = data['price']
        sim_results = []
        progress_bar = st.progress(0)
        
        # Ejecución del motor estocástico
        for i in range(n_sims):
            # 1. Simulamos g1 (Crecimiento Etapa 1) centrado en 11.5%
            g_sim = np.random.normal(0.115, 0.015) 
            # 2. Simulamos WACC centrado en 7.0% (Perfil AAA)
            w_sim = np.random.normal(0.070, 0.003) 
            # 3. Crecimiento Terminal fijo para estabilidad en 3%
            gt_sim = 0.03
            
            try:
                # Validación matemática: Solo simular si el escenario converge (WACC > G Terminal)
                if w_sim > gt_sim:
                    res_dcf = ValuationOracle.run_macro_dcf(
                        data['fcf_now_b'], g_sim, 0.08, w_sim, gt_sim, macro_adj=macro_adj
                    )
                    # Extraer el Fair Price del retorno del DCF
                    fv_escenario = res_dcf[0] if isinstance(res_dcf, (list, tuple)) else res_dcf
                    
                    if not np.isnan(fv_escenario) and fv_escenario > 0:
                        sim_results.append(fv_escenario)
            except:
                continue
            
            if i % 100 == 0:
                progress_bar.progress((i + 1) / n_sims)
        
        progress_bar.empty()
        
        if len(sim_results) > 0:
            sim_series = pd.Series(sim_results)
            media_sim = sim_series.mean()

            # 2. Análisis de Probabilidad de Éxito
            st.markdown(f"**Margen de Seguridad Estadístico (Semilla: {st.session_state['mc_seed_tab8']})**")
            st.info(f"Evaluamos la **Probabilidad de Éxito** comparando el Valor Intrínseco frente al precio actual de mercado de **${precio_actual:,.2f}**.")
            
            c_mc1, c_mc2 = st.columns([2, 1])
            
            with c_mc1:
                umbral_mc = st.slider(
                    "Umbral de Evaluación (Precio de Entrada USD):", 
                    min_value=float(sim_series.min()), 
                    max_value=float(sim_series.max()), 
                    value=float(precio_actual),
                    step=5.0
                )
            
            exitos = (sim_series > umbral_mc).sum()
            prob_exito = (exitos / len(sim_series)) * 100
            
            with c_mc2:
                st.metric(
                    label="🎯 Probabilidad de Éxito", 
                    value=f"{prob_exito:.1f}%",
                    delta=f"Base Case: ${media_sim:,.2f}",
                    delta_color="normal"
                )

            # 3. Visualización: Histograma de Probabilidades
            fig_mc = px.histogram(
                sim_series, 
                nbins=40,
                title="Distribución de Probabilidades: Fair Value vs Umbral de Éxito",
                color_discrete_sequence=['#005BAA'],
                opacity=0.85
            )
            
            fig_mc.add_vline(x=media_sim, line_color="#2ecc71", line_width=3, 
                             annotation_text=f"Base Case: ${media_sim:,.0f}", annotation_position="top left")
            fig_mc.add_vline(x=umbral_mc, line_color="#f85149", line_dash="dash", line_width=3,
                             annotation_text=f"Precio Entrada: ${umbral_mc:,.0f}", annotation_position="top right")

            fig_mc.update_layout(
                template="plotly_dark", height=500,
                xaxis=dict(title="Valor Intrínseco Estimado (USD)", tickformat="$,.0f", showgrid=False),
                yaxis=dict(title="Frecuencia de Escenarios"),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_mc, use_container_width=True)

            # 4. Tabla de Escenarios Críticos (Stress Test)
            st.write("**Resumen de Escenarios de Riesgo**")
            
            p10 = sim_series.quantile(0.1)
            p90 = sim_series.quantile(0.9)
            
            df_stress = pd.DataFrame({
                "Escenario": ["Bear Case (P10)", "Base Case (Media)", "Bull Case (P90)"],
                "Fair Value (USD)": [f"${p10:,.2f}", f"${media_sim:,.2f}", f"${p90:,.2f}"],
                "Upside/Downside": [
                    f"{((p10/precio_actual)-1)*100:+.1f}%",
                    f"{((media_sim/precio_actual)-1)*100:+.1f}%",
                    f"{((p90/precio_actual)-1)*100:+.1f}%"
                ]
            })
            st.table(df_stress)
        else:
            st.error("No se pudieron generar escenarios válidos. Revisa los parámetros de WACC y Crecimiento.")
        
# -------------------------------------------------------------------------
    # TAB 10: VALORACIÓN MULTI-MODELO (CONSENSO DCF vs APT)
    # -------------------------------------------------------------------------
    with tabs[9]:
        st.subheader("🔬 Benchmark de Valoración: DCF vs Arbitrage Pricing Theory (APT)")
        
        # Recuperación segura de EPS
        val_eps = data.get('eps_vals', 16.5)
        
        # 1. ENTRADAS DEL MODELO APT
        st.markdown("### 1. Calibración de Factores de Riesgo (APT)")
        a_col1, a_col2 = st.columns([1, 2])
        
        with a_col1:
            st.write("**Sensibilidades (Betas)**")
            b_mkt = st.slider("Beta Mercado (β_m)", 0.5, 1.5, 0.82)
            b_inf = st.slider("Beta Inflación (β_inf)", -0.5, 0.5, -0.15)
            b_gdp = st.slider("Beta Ciclo PIB (β_gdp)", 0.1, 1.0, 0.45)
            
            rf_rate, mkt_prem = 0.042, 0.055 
            ke_apt = rf_rate + (b_mkt * mkt_prem) + (b_inf * (inflation - 0.02)) + (b_gdp * blended_gdp)
            st.metric("Retorno Requerido (Ke)", f"{ke_apt*100:.2f}%")

        with a_col2:
            g_apt = g_terminal 
            f_val_apt = (val_eps * (1 + g_apt)) / (ke_apt - g_apt) if ke_apt > g_apt else float('nan')
            
            # --- GRÁFICO 1: COMPARATIVA DE "FAIR VALUE" (CON COMAS) ---
            modelos = ["Mercado", "DCF (Flujos)", "APT (Macro)", "Analistas"]
            valores = [p_ref, f_val, f_val_apt, data.get('analysts', {}).get('target', 1067)]
            
            fig_bar = go.Figure(go.Bar(
                x=modelos, y=valores,
                marker_color=['#495057', '#005BAA', '#2ecc71', '#f6e05e'],
                # Formato con comas: : , .0f
                text=[f"${v:,.0f}" if not np.isnan(v) else "Error" for v in valores],
                textposition='outside',
                textfont=dict(size=14, weight='normal') # Etiquetas más legibles
            ))
            
            fig_bar.update_layout(
                title="Consenso de Valoración Intrínseca",
                template="plotly_dark", height=350,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(tickformat="$,.0f", tickfont=dict(size=12)) # Eje Y con comas
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()

        # --- GRÁFICO 2: DISPERSIÓN DE UPSIDE (MÁS LEGIBLE) ---
        st.markdown("### 2. Dispersión y Margen de Seguridad")
        c_radar1, c_radar2 = st.columns([2, 1])
        
        with c_radar1:
            upside_dcf = ((f_val / p_ref) - 1) * 100
            upside_apt = ((f_val_apt / p_ref) - 1) * 100
            upside_wallst = ((data.get('analysts', {}).get('target', 1067) / p_ref) - 1) * 100
            
            fig_scat = go.Figure(go.Scatter(
                x=["DCF", "APT", "Wall St"], 
                y=[upside_dcf, upside_apt, upside_wallst],
                mode='markers+text', 
                marker=dict(size=25, color=['#005BAA', '#2ecc71', '#f6e05e'], line=dict(width=2, color='white')),
                # Formato con comas y signo
                text=[f"{upside_dcf:+,.1f}%", f"{upside_apt:+,.1f}%", f"{upside_wallst:+,.1f}%"],
                textposition="top center",
                textfont=dict(size=14, color='white', weight='normal') # Texto más grande y visible
            ))
            
            fig_scat.update_layout(
                title="Upside Proyectado por Modelo (%)",
                template="plotly_dark", height=400,
                yaxis=dict(ticksuffix="%", gridcolor='rgba(255,255,255,0.1)', tickfont=dict(size=13)),
                xaxis=dict(tickfont=dict(size=14, weight='normal')),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_scat, use_container_width=True)

        with c_radar2:
            st.markdown(f"""
            <div style="background-color: var(--secondary-background-color); padding: 20px; border-radius: 15px; border-left: 8px solid #2ecc71; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                <h4 style="margin-top:0; color:#2ecc71;">Veredicto APT</h4>
                <p style="font-size:1.1rem;">Precio sugerido: <br><span style="font-size:2rem; font-weight:bold;">${f_val_apt:,.2f}</span></p>
                <p>Basado en inflación de <b>{inflation*100:.1f}%</b> y PIB de <b>{blended_gdp*100:.1f}%</b>.</p>
                <hr style="opacity:0.2;">
                <small>Nota: Este modelo descuenta beneficios actuales sin capturar la fase de alto crecimiento proyectada en el DCF.</small>
            </div>
            """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # TAB 11: METODOLOGÍA & FUENTES OFICIALES (10-K / SEC)
    # -------------------------------------------------------------------------
    with tabs[10]:
        st.subheader("📑 Documentación Técnica y Fuentes de Verificación")
        
        m_col1, m_col2 = st.columns([1.5, 1], gap="large")
        
        with m_col1:
            st.markdown("""
                ### Framework de Valoración Híbrido
                El sistema utiliza una arquitectura que contrasta el flujo de caja fundamental con el arbitraje por factores macro.
            """)

            with st.expander("📝 Lógica APT vs CAPM: Explicación Detallada", expanded=True):
                st.write("""
                **CAPM (Capital Asset Pricing Model):** Modelo de un solo factor basado en el riesgo de mercado ($\beta$). 
                Útil para medir volatilidad sistémica, pero limitado ante choques específicos de inflación o consumo.
                
                **APT (Arbitrage Pricing Theory):** Modelo multifactorial que sostiene que el retorno es función de varias primas de riesgo. 
                Permite aislar cómo afectan la **Inflación** o el **PIB** al costo de capital de forma independiente.
                """)
                st.latex(r"E(R_i) = R_f + \sum_{j=1}^{n} \beta_{ij}RP_j")

            st.markdown("""
                ---
                #### 🧮 Resumen Matemático del Modelo
                
                **1. Costo del Patrimonio (CAPM):**
            """)
            st.latex(r"R_e = R_f + \beta \times (E_m - R_f)")

            st.markdown("""
                **2. Modelo Multifactorial (APT Ke):**
            """)
            st.latex(r"K_{e(apt)} = R_f + \beta_m(RP_m) + \beta_{inf}(RP_{inf}) + \beta_{gdp}(RP_{gdp})")

            st.markdown("""
                **3. Costo Promedio Ponderado de Capital (WACC):**
            """)
            st.latex(r"WACC = \left( \frac{E}{V} \times R_e \right) + \left( \frac{D}{V} \times R_d \times (1 - T) \right)")

            st.markdown("""
                **4. Valor Continuo (TV) e Intrínseco (Fair Value):**
            """)
            st.latex(r"TV = \frac{FCF_{10} \times (1 + g)}{WACC - g}")
            st.latex(r"FairValue = \frac{\sum_{t=1}^{10} \frac{FCF_t \times (1 + \text{MacroAdj})}{(1 + WACC)^t} + \frac{TV}{(1 + WACC)^{10}} + \text{Caja} - \text{Deuda}}{\text{Shares}}")
           
            st.markdown("""
                **5. Modelo de Crecimiento de Gordon (Terminal Growth):**
                El modelo asume que los flujos de caja crecerán a una tasa constante ($g$) a perpetuidad después del año 10.
            """)
            st.latex(r"GGM = \frac{D_1}{k - g} \approx \frac{FCF_{10} \times (1 + g_{terminal})}{WACC - g_{terminal}}")

            st.markdown("""
                **6. Valoración Relativa y Benchmarking (Pares):**
                Comparamos los múltiplos de Costco frente a la industria para identificar la 'Prima de Calidad' ($Premium$).
            """)
            st.latex(r"P/E_{Relativo} = \frac{P/E_{COST}}{\text{Promedio } P/E_{Peers}}")
            st.latex(r"EV/EBITDA = \frac{\text{MarketCap} + \text{Deuda} - \text{Caja}}{\text{EBITDA}}")

            st.markdown("""
                **7. Generación de Alpha vs Benchmarks (S&P 500 / Nasdaq):**
                Calculamos el rendimiento excedente que Costco genera sobre el mercado ponderado por su riesgo sistemático ($\beta$).
            """)
            st.latex(r"\text{Alpha} (\alpha) = R_{COST} - [R_f + \beta \times (R_m - R_f)]")
            
            st.info("""
                💡 **Nota de Convergencia:** El modelo Gordon solo es estable si $WACC > g$. 
                La terminal bloquea automáticamente cálculos donde el crecimiento terminal supera el costo de capital para evitar valores infinitos.
            """)       

        with m_col2:
            with st.container(border=True):
                st.write("**📥 Repositorio Interno**")
                pdf_filename = "Guia_Metodologica_COST.pdf"
                try:
                    with open(pdf_filename, "rb") as f:
                        pdf_data = f.read()
                    st.download_button(label="📄 Descargar Guía (PDF)", data=pdf_data, file_name="Guia_Metodologica_COST.pdf", mime="application/pdf", use_container_width=True)
                except FileNotFoundError:
                    st.error(f"⚠️ Archivo '{pdf_filename}' no detectado.")

            st.write("**Gobernanza del Modelo**")
            st.markdown("""
                - **Data Feed:** Yahoo Finance Premium API
                - **Methodology:** Híbrido DCF-APT
                - **Update Frequency:** Real-time (Intraday)
            """)

        st.divider()
        st.caption(f"Terminal Costco Intelligence | Versión 3.4.1 | {datetime.date.today().year}")
        
    # -------------------------------------------------------------------------
    # TAB 12: OPCIONES LAB (FULL GREEKS)
    # -------------------------------------------------------------------------
    with tabs[11]:
        st.subheader("Laboratorio de Griegas y Pricing (Black-Scholes)")
        ok1, ok2, ok3 = st.columns(3)
        strike_p = ok1.number_input("Strike Price ($)", value=float(round(p_ref*1.05, 0)))
        iv_val = ok2.slider("IV (%)", 10, 100, 25) / 100
        t_days = ok3.slider("Días a Expiración", 1, 730, 45)
        g_res = ValuationOracle.calculate_full_greeks(p_ref, strike_p, t_days/365, 0.045, iv_val)
        m_ok1, m_ok2, m_ok3, m_ok4, m_ok5 = st.columns(5)
        m_ok1.metric("Call Price", f"${g_res['price']:.2f}")
        m_ok2.metric("Delta Δ", f"{g_res['delta']:.4f}")
        m_ok3.metric("Gamma γ", f"{g_res['gamma']:.4f}")
        m_ok4.metric("Vega ν", f"{g_res['vega']:.4f}")
        m_ok5.metric("Theta θ", f"{g_res['theta']:.3f}")

if __name__ == "__main__":
    main()
