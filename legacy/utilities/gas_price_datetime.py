import datetime
import os
import time
import requests
import pandas as pd
from pathlib import Path
import sys



API_KEY = os.environ.get('TANKERKOENIG_API_KEY')
if not API_KEY:
    raise RuntimeError(
        "Missing TANKERKOENIG_API_KEY environment variable. Set it before running "
        "this script, e.g. (PowerShell): $env:TANKERKOENIG_API_KEY = 'your-key-here'"
    )

# Gas station UUIDs to record prices for
STATIONS = {
    "Tanke_Lud": "916d61b6-7279-4d63-a754-ae160f8cdee2",
    "Tanke_Steinf": "291fafe3-dbfb-4452-8c68-aa6a7540ce98",
    "Wentorf_Hem": "e1a15081-2543-9107-e040-0b0a3dfe563c",
    "MrWash": "21d8e11f-5712-4d00-81aa-100887b65699",
    "EDEKA_Wentorf": "2f432c0c-9052-466d-9030-c78ab8c4149d",
    "München": "fb79c457-543a-4ff6-ba70-cd270ac2110a",
    "Orlen_Wentorf": "005056ba-7cb6-1ed2-bceb-bbb7e74e0d4e",
}

# Tankerkoenig's prices.php accepts at most 10 comma-separated ids per request
if len(STATIONS) > 10:
    raise RuntimeError("Too many stations for a single prices.php request (max 10)")

# Default station a legacy caller gets if it still asks for a single id
STATION_ID = STATIONS["Tanke_Lud"]

DIESEL_FILE = r"C:\Users\miche\OneDrive\Dokumente\3. Privat\VSC_Projects\Tankpreise\data\processed\diesel_prices_3.csv"
E5_FILE = r"C:\Users\miche\OneDrive\Dokumente\3. Privat\VSC_Projects\Tankpreise\data\processed\e5_prices_1.csv"
E10_FILE = r"C:\Users\miche\OneDrive\Dokumente\3. Privat\VSC_Projects\Tankpreise\data\processed\e10_prices_1.csv"

# Station that historic rows (recorded before multi-station support) belong to
LEGACY_STATION = "Tanke_Lud"


def fetch_current_prices():
    """
    Fetch current prices for all configured STATIONS in a single API call.

    Returns:
        dict mapping station name -> (date, diesel, e5, e10), or
        station name -> (None, None, None, None) if that station is closed
        or missing from the response.
    """
    ids = ",".join(STATIONS.values())
    url = f"https://creativecommons.tankerkoenig.de/json/prices.php?apikey={API_KEY}&ids={ids}"
    resp = requests.get(url, timeout=15).json()

    if not resp.get('ok', False):
        raise RuntimeError("API returned not OK")

    now = datetime.datetime.now()
    results = {}

    for name, station_id in STATIONS.items():
        station_data = resp['prices'].get(station_id)

        if station_data is None:
            print(f"[{now}] {name}: Station ID nicht in der Antwort gefunden.")
            results[name] = (None, None, None, None)
            continue

        if station_data.get('status') != 'open':
            print(f"[{now}] {name}: Tankstelle ist geschlossen - kein Preis erfasst.")
            results[name] = (None, None, None, None)
            continue

        diesel = station_data.get('diesel')
        e5 = station_data.get('e5')
        e10 = station_data.get('e10')
        results[name] = (now, diesel, e5, e10)

    return results


def append_to_csv(filepath, timestamp, station, column, price):
    formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    new_row = pd.DataFrame([[formatted_time, station, price]], columns=['date', 'station', column])

    if Path(filepath).exists():
        df = pd.read_csv(filepath, sep=';', parse_dates=['date'])
        if 'station' not in df.columns:
            # Backfill rows written before multi-station support existed
            df['station'] = LEGACY_STATION
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        df = new_row

    df.to_csv(filepath, index=False, sep=';')


def record_prices_to_csv():
    all_prices = fetch_current_prices()

    for name, (t, diesel, e5, e10) in all_prices.items():
        if t is None:
            continue  # station was closed or missing

        if diesel is not None:
            print(f"[{t}] {name} Dieselpreis: {diesel:.3f} €/L")
            append_to_csv(DIESEL_FILE, t, name, 'diesel', diesel)

        if e5 is not None:
            print(f"[{t}] {name} E5-Preis:    {e5:.3f} €/L")
            append_to_csv(E5_FILE, t, name, 'e5', e5)

        if e10 is not None:
            print(f"[{t}] {name} E10-Preis:   {e10:.3f} €/L")
            append_to_csv(E10_FILE, t, name, 'e10', e10)


record_prices_to_csv()


sys.exit(0)
