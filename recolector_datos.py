import yfinance as yf
import pandas as pd
import time

# Tu universo de inversión definido
tickers_peers = ["WMT", "TGT", "BJ", "KR", "AMZN", "HD", "LOW", "SFM", "DLTR", "DG", "COST"]

def construir_bunker_stats():
    print("🏛️  Iniciando Extracción de ADN Financiero...")
    biblioteca_stats = []

    for t in tickers_peers:
        try:
            print(f"📡 Capturando datos de {t}...")
            asset = yf.Ticker(t)
            info = asset.info
            
            # Recolectamos solo lo que alimenta tus tablas y gráficos
            datos = {
                "Ticker": t,
                "Nombre": info.get('shortName', t),
                "Mkt Cap ($B)": info.get('marketCap', 0) / 1e9,
                "P/E Ratio": info.get('trailingPE', 0),
                "ROE (%)": info.get('returnOnEquity', 0) * 100,
                "Net Margin (%)": info.get('profitMargins', 0) * 100,
                "Div Yield (%)": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
            }
            biblioteca_stats.append(datos)
            time.sleep(1) # Evitar bloqueos
        except Exception as e:
            print(f"❌ Salto en {t}: {e}")

    df_final = pd.DataFrame(biblioteca_stats)
    df_final.to_csv("peers_stats.csv", index=False)
    print("\n✅ ¡Búnker de Peers creado con éxito! (peers_stats.csv)")

if __name__ == "__main__":
    construir_bunker_stats()