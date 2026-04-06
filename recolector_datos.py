import yfinance as yf
import pandas as pd
import time

# Universo extendido: Peers + Índices de Mercado
tickers_peers = ["WMT", "TGT", "BJ", "KR", "AMZN", "HD", "LOW", "SFM", "DLTR", "DG", "COST"]
indices = ["^GSPC", "^IXIC"]
todos_los_activos = tickers_peers + indices

def construir_bunker_completo():
    print("🏛️ Iniciando Operación Búnker: ADN Financiero + Series de Tiempo...")
    
    # --- PARTE A: ESTADÍSTICAS (P/E, ROE, ETC) ---
    biblioteca_stats = []
    for t in tickers_peers:
        try:
            print(f"📡 Capturando fundamentales de {t}...")
            asset = yf.Ticker(t)
            info = asset.info
            
            datos = {
                "Ticker": t,
                "Nombre": info.get('shortName', t),
                "Mkt Cap ($B)": (info.get('marketCap', 0) or 0) / 1e9,
                "P/E Ratio": info.get('trailingPE', 0),
                "ROE (%)": (info.get('returnOnEquity', 0) or 0) * 100,
                "Net Margin (%)": (info.get('profitMargins', 0) or 0) * 100,
                "Div Yield (%)": (info.get('dividendYield', 0) or 0) * 100
            }
            biblioteca_stats.append(datos)
            time.sleep(0.5) 
        except Exception as e:
            print(f"❌ Salto en fundamentales de {t}: {e}")

    pd.DataFrame(biblioteca_stats).to_csv("peers_stats.csv", index=False)
    print("✅ Búnker de fundamentales creado (peers_stats.csv)")

    # --- PARTE B: HISTORIAL DE PRECIOS (PARA GRÁFICAS) ---
    try:
        print(f"\n📡 Descargando series de tiempo para {len(todos_los_activos)} activos...")
        # Descargamos el último año de precios de cierre
        df_history = yf.download(todos_los_activos, period="1y")['Close']
        df_history.to_csv("market_history.csv")
        print("✅ Búnker de historial creado (market_history.csv)")
    except Exception as e:
        print(f"❌ Error al crear historial de mercado: {e}")

if __name__ == "__main__":
    construir_bunker_completo()