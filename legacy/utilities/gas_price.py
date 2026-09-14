import datetime
import os
import time
import requests
import pandas as pd
from pathlib import Path

API_KEY = os.environ.get('TANKERKOENIG_API_KEY')
if not API_KEY:
    raise RuntimeError(
        "Missing TANKERKOENIG_API_KEY environment variable. Set it before running "
        "this script, e.g. (PowerShell): $env:TANKERKOENIG_API_KEY = 'your-key-here'"
    )
STATION_ID = '916d61b6-7279-4d63-a754-ae160f8cdee2'
DATA_FILE = 'diesel_prices_2.csv'


def fetch_current_price():
    url = f"https://creativecommons.tankerkoenig.de/json/prices.php?apikey={API_KEY}&ids={STATION_ID}"
    resp = requests.get(url).json()

    if not resp.get('ok', False):
        raise RuntimeError("API returned not OK")

    station_data = resp['prices'].get(STATION_ID)

    if station_data is None:
        raise RuntimeError("Station ID not found in response")

    if station_data.get('status') != 'open':
        print(f"[{datetime.datetime.now()}] Tankstelle ist geschlossen - kein Preis erfasst.")
        return None, None

    price = station_data.get('diesel')
    timestamp = datetime.datetime.now()
    return timestamp, price


def record_price_to_csv():
    t, p = fetch_current_price()
    if t is None or p is None:
        return  # station was closed

    print(f"[{t}] Dieselpreis: {p:.3f} €/L")
    formatted_time = t.strftime("%Y-%m-%d %H:%M:%S")
    new_row = pd.DataFrame([[formatted_time, p]], columns=['timestamp', 'diesel'])

    if Path(DATA_FILE).exists():
        df = pd.read_csv(DATA_FILE, sep=';', parse_dates=['timestamp'])
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        df = new_row

    df.to_csv(DATA_FILE, index=False, sep=';')


    
record_price_to_csv()





