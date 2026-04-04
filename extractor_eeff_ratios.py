import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm

def load_institutional_data(ticker_symbol):
    try:
        asset = yf.Ticker(ticker_symbol)
        inf = asset.info
        cf_raw = asset.cashflow
        
        # Free Cash Flow (Billones)
        fcf_series = (cf_raw.loc['Operating Cash Flow'] + cf_raw.loc['Capital Expenditure']) / 1e9
        v_h = fcf_series.values[::-1]
        cagr = (v_h[-1]/v_h[0])**(1/(len(v_h)-1)) - 1 if len(v_h) > 1 and v_h[0] > 0 else 0.12
        
        # Recomendaciones de Analistas
        recom = {
            "target_price": inf.get('targetMeanPrice', 0),
            "current_recom": inf.get('recommendationKey', 'N/A').replace('_', ' ').title(),
            "analyst_count": inf.get('numberOfAnalystOpinions', 0),
            "recom_score": inf.get('recommendationMean', 0) # 1=Strong Buy, 5=Sell
        }
        
        return {
            "name": inf.get('longName', 'Costco Wholesale'),
            "price": inf.get('currentPrice', 1014.96),
            "beta": inf.get('beta', 0.978),
            "fcf_now": fcf_series.iloc[0],
            "fcf_hist": fcf_series,
            "cagr_real": cagr,
            "pe": inf.get('trailingPE', 51.8),
            "mkt_cap": inf.get('marketCap', 450e9) / 1e9,
            "is": asset.financials, 
            "bs": asset.balance_sheet, 
            "cf": cf_raw,
            "recommendations": recom,
            "info": inf # Para ratios extra
        }
    except Exception:
        return None

def get_peers_advanced(tickers):
    rows = []
    for t in tickers:
        try:
            obj = yf.Ticker(t); inf = obj.info
            name = "S&P 500" if t == '^GSPC' else "Nasdaq" if t == '^IXIC' else t
            pe = inf.get('trailingPE', 22.5 if t=='^GSPC' else 30.0 if t=='^IXIC' else 20.0)
            growth = inf.get('earningsQuarterlyGrowth', inf.get('revenueGrowth', 0.08)) * 100
            rows.append({'Ticker': name, 'PE': pe, 'Growth': growth})
        except: continue
    return pd.DataFrame(rows)

def calculate_full_greeks(S, K, T, r, sigma, o_type='call'):
    T = max(T, 0.0001)
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    p = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2) if o_type=='call' else K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
    d = norm.cdf(d1) if o_type=='call' else norm.cdf(d1)-1
    g = norm.pdf(d1)/(S*sigma*np.sqrt(T))
    v = (S*np.sqrt(T)*norm.pdf(d1))/100
    th = (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T))) - r*K*np.exp(-r*T)*norm.cdf(d1))/365
    return {"price": p, "delta": d, "gamma": g, "vega": v, "theta": th}
