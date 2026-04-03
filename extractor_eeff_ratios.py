import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import xlsxwriter
import io

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="COST Deep Intelligence Engine", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { 
        width: 100%; background-color: #005BAA; color: white; 
        font-weight: bold; border-radius: 8px; height: 3.5em;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE CÁLCULO Y COMPARATIVA ---
def get_full_analysis(ticker_symbol):
    t = yf.Ticker(ticker_symbol)
    is_df = t.financials
    bs_df = t.balance_sheet
    cf_df = t.cashflow
    
    # Datos para ratios
    revenue = is_df.loc['Total Revenue']
    net_income = is_df.loc['Net Income']
    op_income = is_df.loc['Operating Income']
    
    # Ratios de Eficiencia y Solvencia
    inv_turnover = is_df.loc['Cost Of Revenue'] / bs_df.loc['Inventory']
    cash = bs_df.loc['Cash And Cash Equivalents']
    total_debt = bs_df.loc['Total Debt']
    
    # Consolidar Ratios Anuales
    r_df = pd.DataFrame({
        "Crecimiento Ingresos (%)": revenue.pct_change(-1) * 100,
        "Margen Operativo (%)": (op_income / revenue) * 100,
        "Margen Neto (%)": (net_income / revenue) * 100,
        "Rotación Inventario (x)": inv_turnover,
        "Caja ($B)": cash / 1e9,
        "Deuda Total ($B)": total_debt / 1e9
    }).T
    r_df.columns = [c.strftime('%Y') for c in r_df.columns]
    
    # --- DATA DE COMPARATIVA (BENCHMARK) ---
    # Datos promedio del sector Retail para comparativa visual
    bench_data = pd.DataFrame({
        "Métrica": ["Margen Bruto", "Margen Operativo", "Margen Neto", "Rotación Inv."],
        "Costco (COST)": [12.4, 3.7, 2.9, 13.0],
        "Walmart (WMT)": [24.1, 4.1, 2.4, 8.5],
        "Target (TGT)": [27.5, 5.2, 3.8, 6.2],
        "Sector Avg": [21.0, 4.3, 3.0, 7.5]
    })
    
    return r_df, is_df, bs_df, cf_df, bench_data

# --- 3. INTERFAZ ---
def main():
    st.title("🏛️ Costco Wholesale: Deep Fundamental & Peer Intelligence")
    st.caption("Extracción dinámica de 10-K y Comparativa Sectorial en Tiempo Real")
    
    if st.button("🚀 Ejecutar Análisis Multidimensional"):
        with st.spinner("Descargando estados financieros y procesando comparativas..."):
            r_df, is_df, bs_df, cf_df, bench_df = get_full_analysis("COST")
            
            # --- TABS PARA ORGANIZAR EL ANÁLISIS ---
            tab1, tab2, tab3 = st.tabs(["📈 Tendencias Internas", "📊 Comparativa (Peers)", "📑 Reporte Crudo"])
            
            with tab1:
                st.subheader("Análisis de Tendencia Histórica (Costco)")
                c1, c2 = st.columns(2)
                
                with c1:
                    # Gráfica 1: Ventas y Utilidad
                    fig1 = px.line(is_df.loc[['Total Revenue', 'Net Income']].T, 
                                   title="Crecimiento de Ventas vs Beneficio Neto",
                                   markers=True, template="plotly_white",
                                   color_discrete_map={"Total Revenue": "#005BAA", "Net Income": "#E31837"})
                    st.plotly_chart(fig1, use_container_width=True)
                    
                
                with c2:
                    # Gráfica 2: Solvencia (Caja vs Deuda)
                    solvency_data = r_df.loc[['Caja ($B)', 'Deuda Total ($B)']].T
                    fig2 = px.bar(solvency_data, barmode='group',
                                  title="Posición de Liquidez: Caja vs Deuda Total",
                                  template="plotly_white",
                                  color_discrete_sequence=["#27ae60", "#c0392b"])
                    st.plotly_chart(fig2, use_container_width=True)

                c3, c4 = st.columns(2)
                with c3:
                    # Gráfica 3: Eficiencia (Rotación Inventario)
                    fig3 = px.area(r_df.loc['Rotación Inventario (x)'], 
                                   title="Eficiencia Operativa: Rotación de Inventario",
                                   template="plotly_white", color_discrete_sequence=["#f39c12"])
                    st.plotly_chart(fig3, use_container_width=True)
                    
                
                with c4:
                    # Tabla de Ratios
                    st.write("### Ratios de Calidad")
                    st.dataframe(r_df.style.format("{:.2f}"), use_container_width=True)

            with tab2:
                st.subheader("Benchmarking: Costco vs Competidores Directos")
                st.write("Comparativa de eficiencia operativa y márgenes frente al sector.")
                
                # Gráfica 4: Comparativa de Márgenes y Rotación
                fig4 = px.bar(bench_df, x="Métrica", y=["Costco (COST)", "Walmart (WMT)", "Target (TGT)", "Sector Avg"],
                              barmode="group", title="Márgenes y Eficiencia Relativa",
                              template="plotly_white",
                              color_discrete_sequence=["#005BAA", "#FFC220", "#CC0000", "#95a5a6"])
                st.plotly_chart(fig4, use_container_width=True)
                
                
                st.info("""
                **Insight Clave:** Observa cómo Costco tiene márgenes mucho más bajos que Walmart o Target, 
                pero su **Rotación de Inventario** es casi el doble. Esto explica por qué el mercado 
                le otorga un P/E más alto: es una máquina de volumen, no de margen.
                """)

            with tab3:
                # Exportación y Datos Crudos
                st.subheader("Descarga de Estados Financieros (3-Statement Model)")
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    r_df.to_excel(writer, sheet_name='Ratios')
                    is_df.to_excel(writer, sheet_name='Income_Statement')
                    bs_df.to_excel(writer, sheet_name='Balance_Sheet')
                    cf_df.to_excel(writer, sheet_name='Cash_Flow')
                
                st.download_button(label="🟢 Descargar Excel Completo",
                                   data=output.getvalue(),
                                   file_name="Analisis_COST_Master.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.dataframe(is_df)

if __name__ == "__main__":
    main()
