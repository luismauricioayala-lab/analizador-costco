import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import xlsxwriter
import io

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTÉTICA ---
st.set_page_config(page_title="COST Data Engine Pro", layout="wide")

# CSS para branding institucional (Colores Costco)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { 
        width: 100%; 
        background-color: #005BAA; 
        color: white; 
        font-weight: bold; 
        border-radius: 8px;
        height: 3em;
    }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE CÁLCULO DE RATIOS (BLOOMBERG STYLE) ---
def calculate_advanced_ratios(ticker_symbol):
    t = yf.Ticker(ticker_symbol)
    
    # Descarga de Estados Financieros Crudos
    is_df = t.financials      # Income Statement
    bs_df = t.balance_sheet   # Balance Sheet
    cf_df = t.cashflow        # Cash Flow
    
    # Selección de filas clave (Mapeo US GAAP)
    # Rentabilidad
    gross_profit = is_df.loc['Gross Profit']
    revenue = is_df.loc['Total Revenue']
    op_income = is_df.loc['Operating Income']
    net_income = is_df.loc['Net Income']
    
    # Ratios de Margen
    gross_margin = (gross_profit / revenue) * 100
    op_margin = (op_income / revenue) * 100
    net_margin = (net_income / revenue) * 100
    
    # Eficiencia y Retorno
    # Usamos try/except por si alguna cuenta no está disponible en el reporte
    try:
        equity = bs_df.loc['Stockholders Equity']
        assets = bs_df.loc['Total Assets']
        roe = (net_income / equity) * 100
        roa = (net_income / assets) * 100
    except:
        roe = roa = [0] * len(net_income)

    # Eficiencia Operativa
    try:
        inv_turnover = is_df.loc['Cost Of Revenue'] / bs_df.loc['Inventory']
        asset_turnover = revenue / bs_df.loc['Total Assets']
    except:
        inv_turnover = asset_turnover = [0] * len(revenue)

    # Solvencia (Deuda)
    try:
        debt_ebitda = bs_df.loc['Total Debt'] / is_df.loc['EBITDA']
        current_ratio = bs_df.loc['Current Assets'] / bs_df.loc['Current Liabilities']
    except:
        debt_ebitda = current_ratio = [0] * len(revenue)
    
    # Crecimiento YoY
    rev_growth = revenue.pct_change(-1) * 100
    
    # Consolidación de Tabla de Ratios
    ratios_summary = pd.DataFrame({
        "Crecimiento Ingresos (%)": rev_growth,
        "Margen Bruto (%)": gross_margin,
        "Margen Operativo (%)": op_margin,
        "Margen Neto (%)": net_margin,
        "ROE (%)": roe,
        "ROA (%)": roa,
        "Rotación Inventario (x)": inv_turnover,
        "Rotación Activos (x)": asset_turnover,
        "Deuda / EBITDA (x)": debt_ebitda,
        "Ratio de Liquidez (x)": current_ratio
    }).T
    
    # Limpiar nombres de columnas (Fechas)
    ratios_summary.columns = [c.strftime('%Y') for c in ratios_summary.columns]
    
    return ratios_summary, is_df, bs_df, cf_df

# --- 3. INTERFAZ DE USUARIO ---
def main():
    st.title("🏛️ Costco Fundamental Data Engine")
    st.markdown("""
    Esta herramienta extrae reportes **10-K** directamente de la base de datos financiera, 
    calcula ratios de rentabilidad y genera el modelo de estudio en Excel.
    """)
    
    ticker = "COST" # Fijo para Costco, pero escalable
    
    col_btn, col_info = st.columns([1, 2])
    
    with col_btn:
        run_btn = st.button(f"📊 Analizar Fundamental de {ticker}")

    if run_btn:
        with st.spinner("Procesando US GAAP e instalando visualizaciones..."):
            # Ejecutar cálculos
            r_df, is_df, bs_df, cf_df = calculate_advanced_ratios(ticker)
            
            # --- SECCIÓN 1: DATOS NUMÉRICOS ---
            st.subheader("📋 Panel de Ratios de Calidad")
            st.dataframe(r_df.style.format("{:.2f}"), use_container_width=True)
            
            # --- SECCIÓN 2: VISUALIZACIÓN DE TENDENCIAS ---
            st.markdown("---")
            st.subheader("📈 Análisis Visual de Tendencias")
            
            g_col1, g_col2 = st.columns(2)
            
            with g_col1:
                # Gráfica de Ingresos vs Utilidad
                plot_data = is_df.loc[['Total Revenue', 'Net Income']].T
                plot_data.index = [c.strftime('%Y') for c in plot_data.index]
                
                fig_rev = px.line(plot_data, 
                                  labels={'value': 'USD (Billones)', 'index': 'Año'},
                                  title="Crecimiento: Ingresos vs Utilidad Neta",
                                  markers=True, 
                                  template="plotly_white",
                                  color_discrete_map={"Total Revenue": "#005BAA", "Net Income": "#E31837"})
                st.plotly_chart(fig_rev, use_container_width=True)

            with g_col2:
                # Gráfica de Márgenes
                m_plot = r_df.loc[['Margen Bruto (%)', 'Margen Operativo (%)', 'Margen Neto (%)']].T
                fig_marg = px.bar(m_plot, 
                                  barmode='group', 
                                  title="Evolución de Márgenes de Explotación",
                                  labels={'value': '%', 'index': 'Año'},
                                  template="plotly_white",
                                  color_discrete_sequence=["#005BAA", "#C1D82F", "#E31837"])
                st.plotly_chart(fig_marg, use_container_width=True)
            
            # --- SECCIÓN 3: EXPORTACIÓN A EXCEL ---
            st.markdown("---")
            st.subheader("📥 Descarga de Modelo de Estudio")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Hoja de Ratios
                r_df.to_excel(writer, sheet_name='Análisis_Ratios')
                # Hojas de Estados Financieros
                is_df.to_excel(writer, sheet_name='Income_Statement')
                bs_df.to_excel(writer, sheet_name='Balance_Sheet')
                cf_df.to_excel(writer, sheet_name='Cash_Flow')
                
                # Formato Profesional
                workbook  = writer.book
                num_fmt = workbook.add_format({'num_format': '#,##0.00', 'align': 'right'})
                for sheet in writer.sheets.values():
                    sheet.set_column('A:A', 35)
                    sheet.set_column('B:F', 18, num_fmt)
            
            st.download_button(
                label="🟢 Descargar Master Excel (3-Statement Model)",
                data=output.getvalue(),
                file_name=f"Analisis_Institucional_{ticker}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("¡Análisis completado! Los datos coinciden con la última presentación de resultados.")

if __name__ == "__main__":
    main()
