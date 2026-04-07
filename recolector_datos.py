import yfinance as yf
import pandas as pd
import time
import os

# Universo extendido: Peers (con PSMT) + Índices de Mercado
tickers_peers = ["WMT", "TGT", "BJ", "KR", "AMZN", "HD", "LOW", "SFM", "DLTR", "DG", "COST", "PSMT"]
indices = ["^GSPC", "^IXIC"]
todos_los_activos = tickers_peers + indices

def construir_bunker_completo():
    print("🏛️ Iniciando Operación Búnker: ADN Financiero Fase 2 (PSMT Edition)...")
    
    # --- PARTE A: FUNDAMENTALES PARA LA MATRIZ COMPETITIVA ---
    biblioteca_stats = []
    for t in tickers_peers:
        try:
            print(f"📡 Capturando fundamentales de {t}...")
            asset = yf.Ticker(t)
            info = asset.info
            
            # Extraemos datos con seguros contra valores nulos
            datos = {
                "Ticker": t,
                "Nombre": info.get('shortName', t),
                "Mkt Cap ($B)": (info.get('marketCap', 0) or 0) / 1e9,
                "P/E Ratio": info.get('trailingPE', 0),
                "ROE (%)": (info.get('returnOnEquity', 0) or 0) * 100,
                "Net Margin (%)": (info.get('profitMargins', 0) or 0) * 100,
                "Div Yield (%)": (info.get('dividendYield', 0) or 0) * 100,
                "EV/EBITDA": info.get('enterpriseToEbitda', 0),
                "Price / Revenue": info.get('priceToSalesTrailing12Months', 0),
                "ROA (%)": (info.get('returnOnAssets', 0) or 0) * 100,
                "Current Ratio": info.get('currentRatio', 0),
                "Debt/Equity": info.get('debtToEquity', 0)
            }
            biblioteca_stats.append(datos)
            time.sleep(0.5) 
        except Exception as e:
            print(f"❌ Error en fundamentales de {t}: {e}")

    # Guardar Estadísticas de Peers
    df_stats = pd.DataFrame(biblioteca_stats)
    df_stats.to_csv("peers_stats.csv", index=False)
    print("✅ peers_stats.csv actualizado.")

    # --- PARTE B: HISTORIALES INDIVIDUALES (PARA EL MODO OFFLINE DEL MOTOR) ---
    print(f"\n📂 Generando archivos .csv individuales para el motor de auditoría...")
    for t in tickers_peers:
        try:
            # Descargamos 2 años para tener suficiente historial para Beta y 52w Range
            df_ind = yf.download(t, period="2y", interval="1d", progress=False)
            if not df_ind.empty:
                df_ind.to_csv(f"{t}.csv")
                print(f"   ∟ {t}.csv [OK]")
        except Exception as e:
            print(f"   ∟ ❌ Error en {t}: {e}")

    # --- PARTE C: HISTORIAL CONSOLIDADO (PARA MATRIZ DE CORRELACIÓN) ---
    try:
        print(f"\n📡 Descargando historial consolidado para {len(todos_los_activos)} activos...")
        data = yf.download(todos_los_activos, period="1y", interval="1d", progress=False)
        
        # Manejo de MultiIndex para extraer solo el Cierre
        if isinstance(data.columns, pd.MultiIndex):
            df_history = data['Close']
        else:
            df_history = data
            
        df_history.to_csv("market_history.csv")
        print("✅ market_history.csv actualizado.")
    except Exception as e:
        print(f"❌ Error al crear historial de mercado: {e}")

if __name__ == "__main__":
    construir_bunker_completo()