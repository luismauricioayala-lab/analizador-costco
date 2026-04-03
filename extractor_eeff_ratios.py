import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import streamlit as st
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="COST Ratio Intelligence", layout="wide")

def calculate_advanced_ratios(ticker_symbol):
    t = yf.Ticker(ticker_symbol)
    is_df = t.financials      # Income Statement
    bs_df = t.balance_sheet   # Balance Sheet
    cf_df = t.cashflow        # Cash Flow
    
    # 1. RATIOS DE RENTABILIDAD
    gross_margin = (is_df.loc['Gross Profit'] / is_df.loc['Total Revenue']) * 100
    op_margin = (is_df.loc['Operating Income'] / is_df.loc['Total Revenue']) * 100
    net_margin = (is_df.loc['Net Income'] / is_df.loc['Total Revenue']) * 100
    
    # 2. RENTABILIDAD SOBRE CAPITAL (ROE / ROA)
    roe = (is_df.loc['Net Income'] / bs_df.loc['Stockholders Equity']) * 100
    roa = (is_df.loc['Net Income'] / bs_df.loc['Total Assets']) * 100
    
    # 3. EFICIENCIA (ROTACIÓN)
    asset_turnover = is_df.loc['Total Revenue'] / bs_df.loc['Total Assets']
    inv_turnover = is_df.loc['Cost Of Revenue'] / bs_df.loc['Inventory']
    
    # 4. SOLVENCIA Y LIQUIDEZ
    debt_ebitda = bs_df.loc['Total Debt'] / is_df.loc['EBITDA']
    current_ratio = bs_df.loc['Current Assets'] / bs_df.loc['Current Liabilities']
    
    # 5. CRECIMIENTO INTERANUAL (YoY %)
    rev_growth = is_df.loc['Total Revenue'].pct_change(-1) * 100
    eps_growth = is_df.loc['Basic EPS'].pct_change(-1) * 100
    
    # Unificar en un DataFrame amigable (Estilo Terminal)
    ratios = pd.DataFrame({
        "Crecimiento Ingresos (%)": rev_growth,
        "Crecimiento EPS (%)": eps_growth,
        "Margen Bruto (%)": gross_margin,
        "Margen Operativo (%)": op_margin,
        "Margen Neto (%)": net_margin,
        "ROE (%)": roe,
        "ROA (%)": roa,
        "Rotación Activos (x)": asset_turnover,
        "Rotación Inventario (x)": inv_turnover,
        "Deuda / EBITDA (x)": debt_ebitda,
        "Ratio Actual (Liquidez)": current_ratio
    }).T
    
    return ratios, is_df, bs_df, cf_df
      
    # --- NUEVA SECCIÓN DE GRÁFICAS ---
        st.markdown("---")
        st.subheader("📈 Análisis de Tendencias Visual")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            # Gráfica de Ingresos y Utilidad Neta
            df_plot = is_df.loc[['Total Revenue', 'Net Income']].T
            fig_rev = px.line(df_plot, title="Ventas vs Utilidad Neta (Evolución)", 
                              markers=True, template="plotly_white",
                              color_discrete_map={"Total Revenue": "#005BAA", "Net Income": "#E31837"})
            st.plotly_chart(fig_rev, use_container_width=True)
            
        with col_g2:
            # Gráfica de Márgenes
            margins = r_df.loc[['Margen Bruto (%)', 'Margen Operativo (%)', 'Margen Neto (%)']].T
            fig_marg = px.bar(margins, barmode='group', title="Estructura de Márgenes (%)",
                              template="plotly_white")
            st.plotly_chart(fig_marg, use_container_width=True)






# --- INTERFAZ STREAMLIT ---
st.title("🏛️ Extractor de Ratios Pro — Estilo Bloomberg")
st.info("Generando métricas de Rentabilidad, Eficiencia y Valuación para COST.")

if st.button("📥 Ejecutar Análisis de Ratios"):
    with st.spinner("Mapeando cuentas US GAAP y calculando métricas..."):
        r_df, is_df, bs_df, cf_df = calculate_advanced_ratios("COST")
        
        st.subheader("🔥 Panel de Ratios Calculados (Últimos 4 años)")
        st.dataframe(r_df.style.format("{:.2f}"))
        
        # Exportación a Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            r_df.to_excel(writer, sheet_name='RATIOS_ANALISIS')
            is_df.to_excel(writer, sheet_name='Income_Statement')
            bs_df.to_excel(writer, sheet_name='Balance_Sheet')
            cf_df.to_excel(writer, sheet_name='Cash_Flow')
        
        st.download_button(
            label="💾 Descargar Suite de Ratios en Excel",
            data=output.getvalue(),
            file_name="COST_Deep_Analysis_Ratios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
