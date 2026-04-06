# 🏛️ COST Institutional Master Terminal
**Terminal de Inteligencia Financiera Avanzada para Costco Wholesale Corporation**

Este repositorio contiene una plataforma analítica de grado bancario desarrollada en Python y Streamlit. La terminal integra modelos de valoración estocástica, análisis macroeconómico reactivo y auditoría de estados financieros en tiempo real.

## 🚀 Funcionalidades Clave
* **Valoración Híbrida:** Modelo DCF (Two-Stage) con rampa de transición lineal y modelo APT (Arbitrage Pricing Theory).
* **Análisis de Sensibilidad:** Matriz dinámica de WACC vs. Crecimiento.
* **Simulación Monte Carlo:** 1,000 escenarios estocásticos para determinar el margen de seguridad.
* **Stress Test:** Simulador de "Cisnes Negros" (Ataques cibernéticos, Lockdowns, Crisis de membresía).
* **Laboratorio de Opciones:** Cálculo de Griegas (Δ, γ, ν, θ) mediante Black-Scholes.

## 🛠️ Stack Tecnológico
* **Lenguaje:** Python 3.9+
* **Framework:** Streamlit (UI/UX Institucional)
* **Datos:** Yahoo Finance API (yfinance)
* **Visualización:** Plotly Graph Objects & Express
* **Cálculo:** NumPy, Pandas, SciPy

## 📦 Instalación Local
Si deseas ejecutar la terminal en tu máquina:
1. Clona el repositorio: `git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git`
2. Instala dependencias: `pip install -r requirements.txt`
3. Lanza la app: `streamlit run costco_total_intelligence.py`

## 📄 Metodología
La metodología completa se encuentra detallada en el documento [Guía Metodológica COST](./Guia_Metodologica_COST.pdf).
