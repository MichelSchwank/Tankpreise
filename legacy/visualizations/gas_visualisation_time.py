import pandas as pd
import matplotlib.pyplot as plt
import datetime
from pathlib import Path

DATA_FILE = 'diesel_prices_2.csv'

def show_daily_lows():
    if not Path(DATA_FILE).exists():
        print(f"Datei '{DATA_FILE}' nicht gefunden.")
        return

    # Load and clean
    df = pd.read_csv(DATA_FILE, sep=';')
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['timestamp'])

    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return

    # Filter for last 14 days
    df['date'] = df['timestamp'].dt.date
    cutoff = datetime.date.today() - datetime.timedelta(days=14)
    df = df[df['date'] >= cutoff]

    # Find index of row with minimum price per day
    idx_min = df.groupby('date')['diesel'].idxmin()
    df_min = df.loc[idx_min].copy()

    # Format time for annotation
    df_min['time_str'] = df_min['timestamp'].dt.strftime('%H:%M')
    df_min['date_str'] = df_min['timestamp'].dt.strftime('%d.%m.%Y')
    tage = len(df_min)

    # figure size in inches (800x400 pixels = 8x4 inches at 100 DPI)
    plt.figure(figsize=(8,4), dpi = 100)

    # Plot
    bars = plt.bar(df_min['date_str'].astype(str), df_min['diesel'])

    # Annotate bars with time
    for bar, price, time_str in zip(bars, df_min['diesel'], df_min['time_str']):
        label = f"{price:.3f} €\n{time_str}"
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003, label,
                 ha='center', va='bottom', fontsize=9)
    plt.title(f'Tages-Tiefstpreise Diesel (letzte {tage} Tage)', pad=20)
    plt.ylim(1.5, df_min['diesel'].max() + 0.02)
    plt.ylabel('€/L')
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()

# Run it
show_daily_lows()
