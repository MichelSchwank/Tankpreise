import pandas as pd
import matplotlib.pyplot as plt
import datetime
from pathlib import Path
from datetime import timedelta

DATA_FILE = '2025_06_27_ludgeri.csv'  # <-- adjust if needed
MAX_GAP_MINUTES = 800                    # for grouping identical-price intervals

# ──────────────────────────────────────────────────────────────────────────────
# 1. LOAD + PREPARE  ‒ now includes “shift overnight changes to 09:00” logic
# ──────────────────────────────────────────────────────────────────────────────
def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    if not Path(filepath).exists():
        print(f"Datei '{filepath}' nicht gefunden.")
        return pd.DataFrame()

    # ── read CSV
    df = pd.read_csv(filepath, sep=',', engine='python')

    if 'date' in df.columns:
        df['timestamp'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True)
    else:
        print("Keine 'date'-Spalte gefunden.")
        return pd.DataFrame()

    # ── shift late-night / early-morning entries to next day 09:00
    hour = df['timestamp'].dt.hour
    mask_night = (hour < 8) | (hour >= 22)

    df.loc[mask_night, 'timestamp'] = (
        df.loc[mask_night, 'timestamp'].dt.floor('D')       # 00:00 the same day
        + pd.Timedelta(days=1)                              # move to next day
        + pd.Timedelta(hours=9)                             # 09:00 sharp
    )

    # ── recompute helper columns
    df['date'] = df['timestamp'].dt.date

    # keep only visible time span (06:00-21:30) after shifting
    df = df[(df['timestamp'].dt.time >= datetime.time(9, 0)) &
            (df['timestamp'].dt.time <= datetime.time(22, 00))]

    # limit to last 15 days
    cutoff_date = datetime.date.today() - datetime.timedelta(days=15)
    return df[df['date'] >= cutoff_date]

# ──────────────────────────────────────────────────────────────────────────────
# 2. HELPER: group identical-price timestamps into contiguous intervals
# ──────────────────────────────────────────────────────────────────────────────
def group_close_timestamps(timestamps, max_gap_minutes=MAX_GAP_MINUTES):
    intervals = []
    if not timestamps:
        return intervals

    start = end = timestamps[0]
    for current in timestamps[1:]:
        if (current - end) <= timedelta(minutes=max_gap_minutes):
            end = current
        else:
            intervals.append((start, end))
            start = end = current
    intervals.append((start, end))
    return intervals

# ──────────────────────────────────────────────────────────────────────────────
# 3. HELPER: (optional) dictionary of “cheapest-price intervals” per day
# ──────────────────────────────────────────────────────────────────────────────
def get_daily_min_intervals(df: pd.DataFrame) -> dict:
    interval_dict = {}
    for date, group in df.groupby('date'):
        min_price = group['diesel'].min()
        timestamps = group[group['diesel'] == min_price]['timestamp'].sort_values()
        if not timestamps.empty:
            interval_dict[date] = group_close_timestamps(timestamps.tolist())
    return interval_dict

# ──────────────────────────────────────────────────────────────────────────────
# 4. Build dataframe of each day’s absolute minimum price (for the bars)
# ──────────────────────────────────────────────────────────────────────────────
def prepare_min_price_df(df: pd.DataFrame) -> pd.DataFrame:
    idx_min = df.groupby('date')['diesel'].idxmin()
    min_df = df.loc[idx_min].copy()
    min_df['date_str'] = min_df['timestamp'].dt.strftime('%d.%m.%Y')
    return min_df

# ──────────────────────────────────────────────────────────────────────────────
# 5. PLOT
# ──────────────────────────────────────────────────────────────────────────────
def plot_daily_lows(df: pd.DataFrame, df_min: pd.DataFrame):
    plt.figure(figsize=(15, 5), dpi=100)
    bars = plt.bar(df_min['date_str'], df_min['diesel'])

    for bar, price, date in zip(bars, df_min['diesel'], df_min['date']):
        # bar label
        plt.text(bar.get_x() + bar.get_width() / 2, price - 0.05,
                 f"{price:.3f} €", ha='center', va='center',
                 fontsize=12, color='black')

        # intraday price path (step plot)
        day_data = df[df['date'] == date].sort_values('timestamp')
        if day_data.empty:
            continue

        times       = day_data['timestamp']
        raw_prices  = day_data['diesel']
        minutes     = times.dt.hour * 60 + times.dt.minute
        normalized  = (minutes - minutes.min()) / (minutes.max() - minutes.min() + 1e-5)
        x_values    = bar.get_x() + normalized * bar.get_width()

        plt.step(x_values, raw_prices, where='post', color='black', linewidth=1.5)

        # time labels (you can thin these out if they clutter)
        for x, y, t in zip(x_values, raw_prices, times.dt.strftime('%H:%M')):
            plt.text(x, y - 0.003, t, fontsize=7,
                     ha='center', va='top', rotation=45)

    # layout
    plt.ylim(1.3, 1.8)
    plt.title(f'Tages-Tiefstpreise Diesel (letzte {len(df_min)} Tage)', pad=20)
    plt.ylabel('€/L')
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.show()

# ──────────────────────────────────────────────────────────────────────────────
# 6. DRIVER
# ──────────────────────────────────────────────────────────────────────────────
def show_daily_lows():
    df = load_and_prepare_data(DATA_FILE)
    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return
    df_min = prepare_min_price_df(df)
    plot_daily_lows(df, df_min)

if __name__ == '__main__':
    show_daily_lows()
