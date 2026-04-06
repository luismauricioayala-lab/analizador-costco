import yfinance as yf
import pandas as pd
import time

# Universo extendido: Peers + Índices de Mercado
tickers_peers = ["WMT", "TGT", "BJ", "KR", "AMZN", "HD", "LOW", "SFM", "DLTR", "DG", "COST"]
indices = ["^GSPC", "^IXIC"]
todos_los_activos = tickers_peers + indices

def construir_bunker_completo():
    print("🏛️ Iniciando Operación Búnker: ADN Financiero Extendido...")
    
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
                
                # --- NUEVAS MÉTRICAS DE ALTA RESOLUCIÓN ---
                "EV/EBITDA": info.get('enterpriseToEbitda', 0),
                "Price / Revenue": info.get('priceToSalesTrailing12Months', 0),
                "Asset Turnover": info.get('assetTurnover', 0),
                "ROA (%)": (info.get('returnOnAssets', 0) or 0) * 100,
                "Current Ratio": info.get('currentRatio', 0),
                "Debt/Equity": info.get('debtToEquity', 0)
            }
            biblioteca_stats.append(datos)
            time.sleep(0.7) # Un poco más de respiro para evitar bloqueos
        except Exception as e:
            print(f"❌ Error en fundamentales de {t}: {e}")

    # Guardar Estadísticas
    df_stats = pd.DataFrame(biblioteca_stats)
    df_stats.to_csv("peers_stats.csv", index=False)
    print("✅ Búnker de fundamentales creado (peers_stats.csv)")

    # --- PARTE B: HISTORIAL DE PRECIOS ---
    try:
        print(f"\n📡 Descargando series de tiempo para {len(todos_los_activos)} activos...")
        data = yf.download(todos_los_activos, period="1y", interval="1d", progress=False)
        
        # Manejo de MultiIndex en las columnas de yfinance
        if isinstance(data.columns, pd.MultiIndex):
            df_history = data['Close']
        else:
            df_history = data # Caso poco probable pero seguro
            
        df_history.to_csv("market_history.csv")
        print("✅ Búnker de historial creado (market_history.csv)")
    except Exception as e:
        print(f"❌ Error al crear historial de mercado: {e}")

if __name__ == "__main__":
    construir_bunker_completo()