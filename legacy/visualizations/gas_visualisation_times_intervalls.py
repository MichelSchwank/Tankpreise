import pandas as pd
import matplotlib.pyplot as plt
import datetime
from pathlib import Path
from datetime import timedelta

DATA_FILE = 'diesel_prices_2.csv'

def group_times(times, max_gap_minutes=280):
    intervals = []
    if not times:
        return intervals

    start = times[0]
    end = start
    for t in times[1:]:
        if (t - end) <= timedelta(minutes=max_gap_minutes):
            end = t
        else:
            intervals.append((start, end))
            start = t
            end = t
    intervals.append((start, end))
    return intervals


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

    # Tiefpreis-Zeitintervalle vorbereiten
    interval_dict = {}
    for date, group in df.groupby('date'):
        min_price = group['diesel'].min()
        times = group[group['diesel'] == min_price]['timestamp'].sort_values()
        if times.empty:
            continue
        grouped = group_times(times.tolist())
        interval_dict[date] = grouped

    # Find daily lows
    idx_min = df.groupby('date')['diesel'].idxmin()
    df_min = df.loc[idx_min].copy()
    df_min['date_str'] = df_min['timestamp'].dt.strftime('%d.%m.%Y')

    # Plot
    plt.figure(figsize=(8, 4), dpi=100)
    bars = plt.bar(df_min['date_str'], df_min['diesel'])

    for bar, price, date in zip(bars, df_min['diesel'], df_min['date']):
        intervals = interval_dict.get(date, [])
        interval_strs = [f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in intervals]
        label = f"{price:.3f} €\n" + "\n".join(interval_strs)
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                 label, ha='center', va='bottom', fontsize=8)

    # Styling
    tage = len(df_min)
    plt.ylim(1.5, df_min['diesel'].max() + 0.025)
    plt.title(f'Tages-Tiefstpreise Diesel (letzte {tage} Tage)', pad=20)
    plt.ylabel('€/L')
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()

# Run it
show_daily_lows()
