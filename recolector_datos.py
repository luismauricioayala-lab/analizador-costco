import yfinance as yf
import time
import os

# 1. LA LISTA MAESTRA (Tu universo de inversión)
tickers_interes = [
    "COST", "SPY", "QQQ", "WMT", "TGT", "BJ", 
    "KR", "AMZN", "HD", "LOW", "SFM", "DLTR", "DG"
]

def descargar_universo():
    print("🏛️ Iniciando Operación Búnker: Descarga de Históricos...")
    
    for ticker in tickers_interes:
        print(f"📥 Descargando {ticker}...")
        try:
            # Bajamos el máximo historial disponible para un análisis profundo
            asset = yf.Ticker(ticker)
            df = asset.history(period="max")
            
            if not df.empty:
                nombre_archivo = f"{ticker}.csv"
                df.to_csv(nombre_archivo)
                print(f"✅ {ticker} guardado con {len(df)} registros.")
            else:
                print(f"⚠️ {ticker} devolvió un archivo vacío.")
            
            # Pausa de seguridad para no alertar a los servidores de Yahoo
            time.sleep(2) 
            
        except Exception as e:
            print(f"❌ Error con {ticker}: {e}")

if __name__ == "__main__":
    descargar_universo()
    print("\n🎯 Proceso completado. Todos los CSVs están en la carpeta raíz.")
