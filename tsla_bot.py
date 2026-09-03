import os
import json
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yfinance as yf
import pandas as pd
from datetime import datetime, time, timedelta
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LAST_TRADE_PATH = os.path.join(BASE_DIR, "last_trade.json")

API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
BASE_URL = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY,
    "Content-Type": "application/json"
}

SYMBOL = "TSLA"

def log(msg):
    timestamp = datetime.now(pytz.timezone('America/New_York')).strftime("%Y-%m-%d %H:%M:%S EST")
    print(f"[{timestamp}] {msg}")

def check_credentials():
    if not API_KEY or not SECRET_KEY:
        log("ERROR: Las variables de entorno ALPACA_API_KEY o ALPACA_SECRET_KEY no están configuradas.")
        return False
    return True

def get_alpaca_account():
    url = f"{BASE_URL}/v2/account"
    r = requests.get(url, headers=HEADERS, verify=False)
    if r.status_code == 200:
        try:
            return r.json()
        except Exception as e:
            raise ValueError(f"Error decodificando cuenta JSON: {r.text[:200]}")
    raise ValueError(f"Error consultando cuenta de Alpaca. Código: {r.status_code}. Respuesta: {r.text[:200]}")

def get_positions():
    url = f"{BASE_URL}/v2/positions"
    r = requests.get(url, headers=HEADERS, verify=False)
    if r.status_code == 200:
        try:
            return r.json()
        except Exception:
            return []
    return []

def get_position(symbol=SYMBOL):
    positions = get_positions()
    for pos in positions:
        if pos['symbol'] == symbol:
            return pos
    return None

def get_open_orders(symbol=SYMBOL):
    url = f"{BASE_URL}/v2/orders?status=open&symbols={symbol}"
    r = requests.get(url, headers=HEADERS, verify=False)
    if r.status_code == 200:
        try:
            return r.json()
        except Exception:
            return []
    return []

def cancel_all_orders_for_symbol(symbol=SYMBOL):
    url = f"{BASE_URL}/v2/orders?status=open&symbols={symbol}"
    r = requests.get(url, headers=HEADERS, verify=False)
    if r.status_code == 200:
        try:
            orders = r.json()
            for order in orders:
                cancel_url = f"{BASE_URL}/v2/orders/{order['id']}"
                requests.delete(cancel_url, headers=HEADERS, verify=False)
                log(f"[{symbol}] Cancelada orden abierta ID: {order['id']}")
        except Exception as e:
            log(f"[{symbol}] Error cancelando órdenes: {e}")

def submit_bracket_limit_order(symbol, qty, limit_price, sl_price, tp_price, side="buy"):
    url = f"{BASE_URL}/v2/orders"
    payload = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": "limit",
        "limit_price": f"{limit_price:.2f}",
        "time_in_force": "day",
        "order_class": "bracket",
        "take_profit": {
            "limit_price": f"{tp_price:.2f}"
        },
        "stop_loss": {
            "stop_price": f"{sl_price:.2f}"
        }
    }
    r = requests.post(url, headers=HEADERS, json=payload, verify=False)
    if r.status_code in [200, 201]:
        return r.json()
    else:
        raise ValueError(f"Error enviando orden bracket ({symbol}): {r.text}")

def submit_market_order(symbol, qty, side):
    url = f"{BASE_URL}/v2/orders"
    payload = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": "market",
        "time_in_force": "day"
    }
    r = requests.post(url, headers=HEADERS, json=payload, verify=False)
    if r.status_code in [200, 201]:
        return r.json()
    else:
        raise ValueError(f"Error enviando orden a mercado ({symbol}): {r.text}")

def get_current_data(ticker=SYMBOL, period="5d", interval="5m"):
    session = requests.Session()
    session.verify = False
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
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

def main():
    if not check_credentials():
        return
        
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

    if not config.get("active", True):
        log("El bot de Tesla está desactivado en config.json. Saliendo.")
        return

    tz_ny = pytz.timezone('America/New_York')
    now = datetime.now(tz_ny)
    current_date = now.date()
    current_time = now.time()
    
    t_start = datetime.strptime(config["session_start_est"], "%H:%M").time()
    t_range_end = datetime.strptime(config["session_range_end_est"], "%H:%M").time()
    t_end = datetime.strptime(config["session_end_est"], "%H:%M").time()
    
    # Comprobar si estamos en día laboral (Lunes=0 a Viernes=4)
    if now.weekday() > 4:
        log("Fin de semana. Mercado de Nueva York cerrado.")
        return
        
    # Comprobar si estamos fuera del horario de sesión regular (09:30 a 15:55 EST)
    if current_time < t_start or current_time > t_end:
        log(f"Fuera de horario de la sesión de Nueva York (09:30 - 15:55 EST). Hora actual: {current_time.strftime('%H:%M:%S')}")
        
        # Si es después de las 15:55 EST, cancelar órdenes abiertas y cerrar posiciones
        if current_time > t_end:
            cancel_all_orders_for_symbol(SYMBOL)
            pos = get_position(SYMBOL)
            if pos is not None:
                log(f"[{SYMBOL}] Fin de sesión: Cerrando posición de {pos['qty']} acciones a mercado...")
                qty_close = abs(int(float(pos['qty'])))
                if qty_close > 0:
                    submit_market_order(SYMBOL, qty_close, "sell")
                    log(f"[{SYMBOL}] Posición cerrada.")
        return

    log(f"Ejecución en sesión de Nueva York para {SYMBOL}. Fecha: {current_date}")

    # 1. Consultar posición de TSLA en Alpaca
    pos = get_position(SYMBOL)
    if pos is not None:
        log(f"[{SYMBOL}] Posición activa detectada ({pos['qty']} acciones). Bracket Order en control en el servidor.")
        return
        
    # 2. Verificar si ya existe una orden límite abierta
    open_orders = get_open_orders(SYMBOL)
    if len(open_orders) > 0:
        log(f"[{SYMBOL}] Ya existe {len(open_orders)} orden(es) abierta(s) esperando ejecución. No se duplica orden.")
        return
        
    # 3. Comprobar si ya se operó hoy
    last_trade_date = ""
    if os.path.exists(LAST_TRADE_PATH):
        with open(LAST_TRADE_PATH, 'r') as f:
            try:
                last_trade_date = json.load(f).get("last_trade_date", "")
            except Exception:
                last_trade_date = ""

    if last_trade_date == str(current_date):
        log(f"[{SYMBOL}] Límite de 1 operación por día alcanzado para hoy.")
        return
        
    # 4. Descargar datos de 5 minutos
    try:
        df = get_current_data(SYMBOL, period="5d", interval="5m")
    except Exception as e:
        log(f"[{SYMBOL}] Error descargando datos: {e}")
        return
        
    # Filtrar velas de hoy
    today_candles = df[df.index.date == current_date].sort_index()
    
    # Rango de Apertura (09:30 a 09:45)
    opening_range = today_candles[(today_candles.index.time >= t_start) & (today_candles.index.time <= t_range_end)]
    if len(opening_range) < 3:
        log(f"[{SYMBOL}] Esperando a que se complete el rango de apertura (09:30 - 09:45 EST)...")
        return
        
    range_high = float(opening_range['High'].max())
    range_low = float(opening_range['Low'].min())
    log(f"[{SYMBOL}] Rango 15m: Alto = ${range_high:.2f} | Bajo = ${range_low:.2f}")
    
    # Velas posteriores al rango (09:45 en adelante)
    post_range = today_candles[(today_candles.index.time > t_range_end) & (today_candles.index.time <= t_end)]
    if len(post_range) < 3:
        log(f"[{SYMBOL}] Esperando formación de velas posteriores a las 09:45 EST...")
        return
        
    r_factor = config.get("r_factor", 2.5)
    risk_pct = config.get("risk_per_trade_pct", 2.0)
    
    # Buscar patrón FVG Alcista
    for i in range(2, len(post_range)):
        c_t = post_range.iloc[i]
        c_t1 = post_range.iloc[i-1]
        c_t2 = post_range.iloc[i-2]
        
        close_t = float(c_t['Close'])
        close_t1 = float(c_t1['Close'])
        
        is_breakout = (close_t > range_high or close_t1 > range_high)
        low_t = float(c_t['Low'])
        high_t2 = float(c_t2['High'])
        
        if is_breakout and low_t > high_t2:
            entry_price = round(low_t, 2)
            sl_price = round(high_t2, 2)
            risk_pts = entry_price - sl_price
            
            if risk_pts > 0:
                tp_price = round(entry_price + r_factor * risk_pts, 2)
                
                log(f"[{SYMBOL}] ¡FVG Alcista Detectado a las {post_range.index[i].time()}!")
                log(f"[{SYMBOL}] -> Entrada Límite: ${entry_price:.2f} | SL: ${sl_price:.2f} | TP: ${tp_price:.2f}")
                
                # Consultar cuenta de Alpaca
                try:
                    acc = get_alpaca_account()
                    cash_balance = float(acc['cash'])
                    buying_power = float(acc.get('buying_power', cash_balance))
                    log(f"Balance Alpaca: Cash = ${cash_balance:.2f} USD | Buying Power = ${buying_power:.2f} USD")
                except Exception as e:
                    log(f"Error consultando cuenta Alpaca: {e}")
                    return
                    
                capital_base = min(300.0, cash_balance)
                if capital_base < 10.0:
                    log(f"[{SYMBOL}] Capital insuficiente para operar.")
                    return
                    
                risk_usd = capital_base * (risk_pct / 100.0)
                qty = risk_usd / risk_pts
                
                if qty * entry_price > buying_power:
                    qty = buying_power / entry_price
                    
                qty = int(qty)
                if qty < 1:
                    if buying_power >= entry_price:
                        qty = 1
                        log(f"[{SYMBOL}] Ajustando a 1 acción mínima.")
                    else:
                        log(f"[{SYMBOL}] Saldo insuficiente para comprar 1 acción de Tesla.")
                        return
                        
                log(f"[{SYMBOL}] Enviando Orden Límite Bracket: {qty} acciones @ ${entry_price:.2f}...")
                try:
                    res = submit_bracket_limit_order(SYMBOL, qty, entry_price, sl_price, tp_price)
                    log(f"[{SYMBOL}] Orden Bracket enviada exitosamente. ID: {res['id']}")
                    
                    with open(LAST_TRADE_PATH, 'w') as f:
                        json.dump({"last_trade_date": str(current_date)}, f, indent=2)
                    break
                except Exception as e:
                    log(f"[{SYMBOL}] Error enviando orden: {e}")
                    return

if __name__ == "__main__":
    main()
