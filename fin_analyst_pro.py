import streamlit as st
import numpy as np
from scipy.stats import norm
import pandas as pd

def run_didactic_app():
    st.set_page_config(page_title="Academia Financiera: Costco", layout="wide")
    st.title("🎓 Academia de Inversión: Costco (COST)")
    
    # --- SIDEBAR (Contexto Didáctico) ---
    st.sidebar.header("📖 Glosario Rápido")
    with st.sidebar.expander("¿Qué es el Valor Intrínseco?"):
        st.write("Es lo que la empresa 'realmente' vale basado en el dinero que generará en el futuro, no en su precio de hoy.")
    with st.sidebar.expander("¿Qué es una Opción?"):
        st.write("Es un contrato que te da el DERECHO (pero no la obligación) de comprar una acción a un precio fijo.")

    market_price = st.sidebar.number_input("Precio Actual de la Acción (USD)", value=850.0)
    
    # Reordenamos: Valoración -> Benchmarking -> Veredicto -> Opciones
    tab1, tab2, tab3, tab4 = st.tabs(["🏢 1. Valoración (DCF)", "📈 2. Benchmarking", "⚖️ 3. Veredicto", "📊 4. Opciones"])

    # --- TAB 1: VALORACIÓN ---
    with tab1:
        st.header("¿Cuánto vale realmente el negocio?")
        st.info("💡 **Concepto:** El modelo DCF asume que Costco es una 'máquina de dinero'. Sumamos todo el efectivo que producirá en los próximos años y lo traemos al valor de hoy.")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            growth = st.slider("Crecimiento Esperado (%)", 1, 20, 9, help="¿Qué tanto crees que crezcan las ventas anuales?") / 100
            wacc = st.slider("Tasa de Descuento (%)", 5, 12, 8, help="El riesgo. A mayor riesgo, mayor tasa y menor valor hoy.") / 100
        
        # Lógica DCF
        fcf_margin, shares = 0.04, 0.443
        fcf_future = [260 * (1 + growth)**i * fcf_margin for i in range(1, 6)]
        tv = (fcf_future[-1] * 1.02) / (wacc - 0.02)
        pv = sum([fcf / (1 + wacc)**(i+1) for i, fcf in enumerate(fcf_future)]) + (tv / (1 + wacc)**5)
        fair_value = pv / shares
        
        with col_f2:
            st.metric("Precio Justo Estimado", f"${fair_value:.2f}")
            if fair_value > market_price:
                st.success(f"La acción parece estar barata. Tiene un margen de seguridad del {((fair_value/market_price)-1)*100:.1f}%")
            else:
                st.error("La acción parece estar cara según sus flujos futuros.")

    # --- TAB 2: BENCHMARKING ---
    with tab2:
        st.header("Costco vs Sus Competidores")
        st.info("💡 **Concepto:** Una empresa puede ser buena, pero ¿es la mejor de su sector? Aquí comparamos múltiplos como el P/E (cuántos años de ganancias pagas por la acción).")
        
        comparison_df = pd.DataFrame({
            "Métrica": ["P/E Ratio (Precio/Ganancia)", "Margen Neto", "Modelo de Negocio"],
            "COST": [52.4, "2.6%", "Membresía (Fiel)"],
            "WMT": [31.2, "2.4%", "Volumen (Retail)"],
            "S&P 500": [21.0, "11.0%", "Promedio Mercado"]
        })
        st.table(comparison_df)
        st.write("**Lección:** Costco casi siempre es más cara (P/E alto) porque sus clientes rara vez se van.")

    # --- TAB 3: VEREDICTO ---
    with tab3:
        st.header("El Juicio Final")
        st.write("Combinamos la valoración matemática con la realidad del mercado.")
        
        score = 0
        if fair_value > market_price: score += 50
        if market_price < 900: score += 50 # Ejemplo de soporte psicológico
        
        st.progress(score / 100)
        if score >= 100:
            st.balloons()
            st.success("¡VEREDICTO: COMPRA FUERTE! Las matemáticas y el precio coinciden.")
        else:
            st.warning("VEREDICTO: OBSERVAR. Espera a que el precio baje o el crecimiento suba.")

    # --- TAB 4: OPCIONES (EL ÚLTIMO) ---
    with tab4:
        st.header("Estrategia con Derivados")
        st.info("💡 **Concepto:** Si ya sabes que Costco es buena, puedes usar Opciones para ganar más con menos dinero, o para protegerte.")
        
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            K = st.number_input("Precio Strike (Precio de ejercicio)", value=860.0)
            t = st.slider("Días al Vencimiento (Tiempo)", 1, 90, 30) / 365
            iv = st.slider("Volatilidad (Miedo del mercado %)", 1, 100, 35) / 100
            
        # Black-Scholes
        r = 0.05
        d1 = (np.log(market_price / K) + (r + 0.5 * iv**2) * t) / (iv * np.sqrt(t))
        d2 = d1 - iv * np.sqrt(t)
        theoretical_call = (market_price * norm.cdf(d1)) - (K * np.exp(-r * t) * norm.cdf(d2))
        delta = norm.cdf(d1)
        
        with col_o2:
            st.subheader("Análisis de Riesgo")
            st.write(f"**Precio Justo del Contrato:** ${theoretical_call:.2f}")
            st.write(f"**Probabilidad de Éxito (Delta):** {delta*100:.1f}%")
            
            with st.expander("¿Qué significa esta Delta?"):
                st.write(f"Hay un {delta*100:.1f}% de probabilidad de que la acción termine por encima de ${K} al vencimiento.")

if __name__ == "__main__":
    run_didactic_app()