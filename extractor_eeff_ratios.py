import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm

def load_institutional_data(symbol):
    """Extrae datos financieros, ratios y sentimiento de analistas."""
    try:
        t = yf.Ticker(symbol)
        inf, cf = t.info, t.cashflow
        fcf = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']) / 1e9
        v = fcf.values[::-1]
        cagr = (v[-1]/v[0])**(1/(len(v)-1))-1 if len(v)>1 else 0.12
        
        return {
            "name": inf.get('longName', symbol), "price": inf.get('currentPrice', 1014.96),
            "beta": inf.get('beta', 0.978), "fcf_now": fcf.iloc[0], "fcf_hist": fcf, "cagr_real": cagr,
            "pe": inf.get('trailingPE', 51.8), "mkt_cap": inf.get('marketCap', 450e9)/1e9,
            "is": t.financials, "bs": t.balance_sheet, "cf": cf, "info": inf,
            "recommendations": {
                "target": inf.get('targetMeanPrice', 0),
                "key": inf.get('recommendationKey', 'N/A').replace('_', ' ').title(),
                "score": inf.get('recommendationMean', 0)
            }
        }
    except: return None

def get_peers_advanced(tickers):
    """Genera benchmark comparativo dinámico."""
    data = []
    for t in tickers:
        try:
            inf = yf.Ticker(t).info
            name = {"^GSPC":"S&P 500", "^IXIC":"Nasdaq"}.get(t, t)
            pe = inf.get('trailingPE', 22.5 if "GSPC" in t else 29.8 if "IXIC" in t else 0)
            g = inf.get('earningsQuarterlyGrowth', inf.get('revenueGrowth', 0.08)) * 100
            data.append({'Ticker': name, 'PE': pe, 'Growth': g if g != 0 else 8.0})
        except: continue
    return pd.DataFrame(data)

def calculate_full_greeks(S, K, T, r, sigma, o_type='call'):
    """Motor matemático Black-Scholes para derivados."""
    T = max(T, 0.0001)
    d1 = (np.log(S/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    p = S*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d2) if o_type=='call' else K*np.exp(-r*T)*norm.cdf(-d2)-S*norm.cdf(-d1)
    d = norm.cdf(d1) if o_type=='call' else norm.cdf(d1)-1
    return {"price": p, "delta": d, "gamma": norm.pdf(d1)/(S*sigma*np.sqrt(T)), 
            "vega": (S*np.sqrt(T)*norm.pdf(d1))/100, 
            "theta": (-(S*norm.pdf(d1)*sigma/(2*np.sqrt(T)))-r*K*np.exp(-r*T)*norm.cdf(d1 if o_type=='call' else -d1))/365}
