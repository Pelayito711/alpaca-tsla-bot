import os
import json
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def download_data(ticker="TSLA", period="30d", interval="5m"):
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    print(f"Descargando datos históricos de {ticker}...")
    df = yf.download(ticker, period=period, interval=interval, session=session)
    if df.empty:
        raise ValueError(f"No se pudieron descargar datos de {ticker}.")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df = df.tz_convert('America/New_York')
        
    return df.sort_index()

def run_fvg_simulation(df, r_factor, risk_per_trade):
    t_start = time(9, 30)
    t_range_end = time(9, 45)
    t_end = time(15, 55)
    
    df = df.copy()
    df['Date'] = df.index.date
    grouped = df.groupby('Date')
    trades = []
    
    for day, group in grouped:
        group = group.sort_index()
        opening_range = group[(group.index.time >= t_start) & (group.index.time <= t_range_end)]
        if len(opening_range) < 3:
            continue
            
        range_high = float(opening_range['High'].max())
        range_low = float(opening_range['Low'].min())
        
        post_range = group[(group.index.time > t_range_end) & (group.index.time <= t_end)]
        if len(post_range) < 3:
            continue
            
        limit_order = None
        in_trade = False
        trade_status = {}
        
        for idx in range(2, len(post_range)):
            c_t = post_range.iloc[idx]
            c_t1 = post_range.iloc[idx - 1]
            c_t2 = post_range.iloc[idx - 2]
            current_time = post_range.index[idx].time()
            
            high_price = float(c_t['High'])
            low_price = float(c_t['Low'])
            close_price = float(c_t['Close'])
            
            if in_trade:
                if low_price <= trade_status['sl']:
                    trades.append(-risk_per_trade)
                    in_trade = False
                    break
                elif high_price >= trade_status['tp']:
                    trades.append(risk_per_trade * r_factor)
                    in_trade = False
                    break
                elif current_time >= t_end:
                    ret = (close_price - trade_status['entry']) / trade_status['entry']
                    risk_ret = (trade_status['entry'] - trade_status['sl']) / trade_status['entry']
                    pnl = (ret / risk_ret) * risk_per_trade if risk_ret > 0 else 0
                    trades.append(pnl)
                    in_trade = False
                    break
            elif limit_order is not None:
                if low_price <= limit_order['entry']:
                    in_trade = True
                    trade_status = limit_order
                    limit_order = None
            else:
                close_t = float(c_t['Close'])
                close_t1 = float(c_t1['Close'])
                is_breakout = (close_t > range_high or close_t1 > range_high)
                
                low_t = float(c_t['Low'])
                high_t2 = float(c_t2['High'])
                
                if is_breakout and low_t > high_t2:
                    entry = low_t
                    sl = high_t2
                    risk_pts = entry - sl
                    if risk_pts > 0:
                        limit_order = {
                            'entry': entry,
                            'sl': sl,
                            'tp': entry + r_factor * risk_pts
                        }
                        
    if not trades:
        return 0.0, 0.0
        
    trades = np.array(trades)
    total_return = np.prod(1 + trades / 100.0) - 1
    wins = trades[trades > 0]
    losses = trades[trades <= 0]
    profit_factor = wins.sum() / abs(losses.sum()) if len(losses) > 0 and losses.sum() != 0 else (99.0 if len(wins) > 0 else 0.0)
    
    return total_return * 100.0, profit_factor

def main():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "ticker": "TSLA",
            "r_factor": 2.5,
            "risk_per_trade_pct": 2.0,
            "session_start_est": "09:30",
            "session_range_end_est": "09:45",
            "session_end_est": "15:55",
            "active": True
        }
        
    print("================================================================")
    print("AUTO-OPTIMIZADOR SEMANAL TESLA (TSLA)")
    print("================================================================\n")
    
    try:
        df = download_data("TSLA")
    except Exception as e:
        print(f"Error descargando datos para TSLA: {e}")
        return
        
    r_factors = [1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
    best_ret = -999.0
    best_r = 2.5
    best_pf = 0.0
    
    for r in r_factors:
        ret, pf = run_fvg_simulation(df, r, risk_per_trade=config.get("risk_per_trade_pct", 2.0))
        print(f"R-Factor {r:.2f} -> Retorno: {ret:+.2f}% | Profit Factor: {pf:.2f}")
        if ret > best_ret:
            best_ret = ret
            best_r = r
            best_pf = pf
            
    print(f"\n-> Parámetro Óptimo Seleccionado: R = {best_r:.2f} (Retorno: {best_ret:+.2f}%, PF: {best_pf:.2f})")
    config["r_factor"] = float(best_r)
    config["active"] = bool(best_pf >= 1.05 and best_ret > 0)
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Configuración actualizada guardada en: {CONFIG_PATH}")

if __name__ == "__main__":
    main()
