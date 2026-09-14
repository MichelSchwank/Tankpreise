import pandas as pd
import matplotlib.pyplot as plt
import datetime
from pathlib import Path
from datetime import timedelta

DATA_FILE = 'diesel_prices_2.csv'
MAX_GAP_MINUTES = 280
ROLLING_AVG_WINDOW = 3

def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    if not Path(filepath).exists():
        print(f"Datei '{filepath}' nicht gefunden.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, sep=';')
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', dayfirst=True)
    df.dropna(subset=['timestamp'], inplace=True)

    df['date'] = df['timestamp'].dt.date
    cutoff_date = datetime.date.today() - datetime.timedelta(days=14)
    return df[df['date'] >= cutoff_date]

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

def get_daily_min_intervals(df: pd.DataFrame) -> dict:
    interval_dict = {}
    for date, group in df.groupby('date'):
        min_price = group['diesel'].min()
        timestamps = group[group['diesel'] == min_price]['timestamp'].sort_values()
        if not timestamps.empty:
            interval_dict[date] = group_close_timestamps(timestamps.tolist())
    return interval_dict

def prepare_min_price_df(df: pd.DataFrame) -> pd.DataFrame:
    idx_min = df.groupby('date')['diesel'].idxmin()
    min_df = df.loc[idx_min].copy()
    min_df['date_str'] = min_df['timestamp'].dt.strftime('%d.%m.%Y')
    return min_df

def plot_daily_lows(df: pd.DataFrame, df_min: pd.DataFrame, interval_dict: dict):
    plt.figure(figsize=(8, 4), dpi=100)
    bars = plt.bar(df_min['date_str'], df_min['diesel'])

    for bar, price, date, label_str in zip(bars, df_min['diesel'], df_min['date'], df_min['date_str']):
        # Display time intervals
        intervals = interval_dict.get(date, [])
        interval_text = "\n".join(f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in intervals)
        label = f"{price:.3f} €\n{interval_text}"

        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                 label, ha='center', va='bottom', fontsize=8)

        # Add line plot overlay for each day's price trend
        day_data = df[df['date'] == date]
        if not day_data.empty:
            times = day_data['timestamp']
            smoothed_prices = day_data['diesel'].rolling(window=ROLLING_AVG_WINDOW, center=True, min_periods=1).mean()
            minutes = times.dt.hour * 60 + times.dt.minute
            normalized_x = (minutes - minutes.min()) / (minutes.max() - minutes.min() + 1e-5)
            x_values = bar.get_x() + normalized_x * bar.get_width()
            y_offset = 0.03
            plt.plot(x_values, smoothed_prices - y_offset, color='black', linewidth=1.5)

    # Finalize plot
    plt.ylim(1.5, df_min['diesel'].max() + 0.025)
    plt.title(f'Tages-Tiefstpreise Diesel (letzte {len(df_min)} Tage)', pad=20)
    plt.ylabel('€/L')
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()

def show_daily_lows():
    df = load_and_prepare_data(DATA_FILE)
    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return

    interval_dict = get_daily_min_intervals(df)
    df_min = prepare_min_price_df(df)
    plot_daily_lows(df, df_min, interval_dict)

if __name__ == '__main__':
    show_daily_lows()
