import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta, time, date

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
# Use path relative to this script file, not working directory
SCRIPT_DIR = Path(__file__).parent
DATA_FILE = SCRIPT_DIR / '../data/processed/diesel_prices_3.csv'   # CSV file path
MAX_GAP_MINUTES = 800                  # Max gap between identical prices in minutes
SEPERATOR = ';'
show_days = 14


# ──────────────────────────────────────────────────────────────────────────────
# 1. Load and preprocess data
# ──────────────────────────────────────────────────────────────────────────────
def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    """
    Load fuel price data from CSV and prepare it:
    - Parse timestamps
    - Shift prices outside 09:00–21:59 to next day 09:00
    - Add 22:00 clones with last known daily price
    - Filter to recent days (configurable) and 09:00–22:00 range
    """
    if not Path(filepath).exists():
        print(f"Datei '{filepath}' nicht gefunden.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, sep=SEPERATOR, engine='python')

    if 'date' not in df.columns:
        print("Keine 'date'-Spalte gefunden.")
        return pd.DataFrame()

    df['timestamp'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True).dt.tz_localize(None)
    df.dropna(subset=['timestamp'], inplace=True)

    # Shift late/early entries to 09:00 next day
    
    night_mask =  (df['timestamp'].dt.time < time(8, 0)) | (df['timestamp'].dt.time >= time(22, 1))
    df.loc[night_mask, 'timestamp'] = (
        df.loc[night_mask, 'timestamp'].dt.floor('D')
        + timedelta(days=1, hours=9)
    )

    # Update helper columns
    df['date'] = df['timestamp'].dt.date

    # Keep only 09:00–22:00 entries
    df = df[(df['timestamp'].dt.time >= time(9, 0)) & (df['timestamp'].dt.time <= time(22, 0))]

    # Filter to configured number of days
    cutoff = date.today() - timedelta(days=show_days)
    df = df[df['date'] >= cutoff]

    # Add synthetic 22:00 entries
    new_rows = []
    for day, group in df.groupby('date'):
        latest = group.loc[group['timestamp'].idxmax()]
        if latest['timestamp'].time() < time(22, 0):
            clone = latest.copy()
            clone['timestamp'] = datetime.combine(day, time(22, 0))
            new_rows.append(clone)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 2. Group contiguous timestamps with same price
# ──────────────────────────────────────────────────────────────────────────────
def group_close_timestamps(timestamps, max_gap_minutes=MAX_GAP_MINUTES):
    """
    Group timestamps into contiguous intervals if their time gaps are below max_gap_minutes.
    """
    if not timestamps:
        return []

    intervals = []
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
# 3. Get cheapest price intervals per day
# ──────────────────────────────────────────────────────────────────────────────
def get_daily_min_intervals(df: pd.DataFrame) -> dict:
    """
    Return a dict of {date: [(start, end), ...]} intervals when the daily minimum price was active.
    """
    result = {}
    for day, group in df.groupby('date'):
        min_price = group['diesel'].min()
        timestamps = group[group['diesel'] == min_price]['timestamp'].sort_values()
        if not timestamps.empty:
            result[day] = group_close_timestamps(timestamps.tolist())
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 4. Prepare daily minimum prices for bar plot
# ──────────────────────────────────────────────────────────────────────────────
def prepare_min_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract a DataFrame with each day's absolute minimum price and a label-ready date string.
    """
    idx_min = df.groupby('date')['diesel'].idxmin()
    min_df = df.loc[idx_min].copy()
    min_df['date_str'] = min_df['timestamp'].dt.strftime('%d.%m.%Y')
    return min_df


# ──────────────────────────────────────────────────────────────────────────────
# 5. Visualize daily minimum diesel prices
# ──────────────────────────────────────────────────────────────────────────────
def plot_daily_lows(df: pd.DataFrame, df_min: pd.DataFrame):
    """
    Create a bar plot of daily minimum diesel prices with overlaid intraday step curves.
    """
    plt.figure(figsize=(15, 5), dpi=100)
    bars = plt.bar(df_min['date_str'], df_min['diesel'])

    for bar, price, day in zip(bars, df_min['diesel'], df_min['date']):
        # Bar label
        plt.text(bar.get_x() + bar.get_width() / 2, price - 0.05,
                 f"{price:.3f} €", ha='center', va='center', fontsize=12)

        # Step plot for price progression
        day_data = df[df['date'] == day].sort_values('timestamp')
        if day_data.empty:
            continue

        times = day_data['timestamp']
        raw_prices = day_data['diesel']
        minutes = times.dt.hour * 60 + times.dt.minute
        normalized = (minutes - minutes.min()) / (minutes.max() - minutes.min() + 1e-5)
        x_values = bar.get_x() + normalized * bar.get_width()

        plt.step(x_values, raw_prices, where='post', color='black', linewidth=1.5)

        # Optional time labels
        for x, y, t in zip(x_values, raw_prices, times.dt.strftime('%H:%M')):
            plt.text(x, y - 0.003, t, fontsize=7, ha='center', va='top', rotation=45)

    plt.ylim(1.3, 1.8)
    plt.title(f'Tages-Tiefstpreise Diesel ({len(df_min)} Tage mit Daten)', pad=20)
    plt.ylabel('€/L')
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.show()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Main entry point
# ──────────────────────────────────────────────────────────────────────────────
def show_daily_lows():
    """
    Load data, compute daily minimums, and show the annotated plot.
    """
    df = load_and_prepare_data(DATA_FILE)
    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return
    df_min = prepare_min_price_df(df)
    plot_daily_lows(df, df_min)


if __name__ == '__main__':
    show_daily_lows()
