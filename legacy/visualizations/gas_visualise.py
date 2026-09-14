import pandas as pd
import matplotlib.pyplot as plt
import datetime
from pathlib import Path

DATA_FILE = 'diesel_prices_2.csv'

def show_daily_lows():
    if not Path(DATA_FILE).exists():
        print(f"Datei '{DATA_FILE}' nicht gefunden.")
        return

    # Read CSV and convert timestamp manually
    df = pd.read_csv(DATA_FILE, sep=';')
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return

    # Filter last 14 days
    df['date'] = df['timestamp'].dt.date
    cutoff = datetime.date.today() - datetime.timedelta(days=14)
    df = df[df['date'] >= cutoff]

    # Group by date and get lowest diesel price
    daily_low = df.groupby('date')['diesel'].min()
    print(daily_low)

    # Plot
    daily_low.plot(kind='bar')
    plt.title('Tages-Tiefstpreise Diesel (letzte 14 Tage)')
    plt.ylabel('€/L')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# Run it
show_daily_lows()
