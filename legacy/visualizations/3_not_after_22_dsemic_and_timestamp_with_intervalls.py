import pandas as pd
import matplotlib.pyplot as plt
import datetime
from pathlib import Path
from datetime import timedelta

DATA_FILE = 'diesel_prices_2.csv'  # Your CSV file path
MAX_GAP_MINUTES = 800

def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    if not Path(filepath).exists():
        print(f"Datei '{filepath}' nicht gefunden.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, sep=';', engine='python')
    
    # Ensure 'timestamp' column exists and convert to datetime
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', dayfirst=True)
    else:
        print("Keine 'timestamp'-Spalte gefunden.")
        return pd.DataFrame()

    # Adjust time and drop invalid timestamps
    df['timestamp'] -= pd.Timedelta(hours=0)
    df.dropna(subset=['timestamp'], inplace=True)

    # Filter by valid time range (06:00 to 21:30)
    df = df[(df['timestamp'].dt.time >= datetime.time(6, 0)) & 
            (df['timestamp'].dt.time <= datetime.time(21, 30))]

    cutoff_date = datetime.date.today() - datetime.timedelta(days=15)
    df['date'] = df['timestamp'].dt.date  # Convert timestamp to date only for grouping
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

def plot_daily_lows(df: pd.DataFrame, df_min: pd.DataFrame):
    plt.figure(figsize=(15, 5), dpi=100)
    bars = plt.bar(df_min['date_str'], df_min['diesel'])

    for bar, price, date, label_str in zip(bars, df_min['diesel'], df_min['date'], df_min['date_str']):
        # Displaying price label in the middle of the bar
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            price - 0.05,  # slightly below top of bar
            f"{price:.3f} €",
            ha='center',
            va='center',
            fontsize=12,
            color='black'
        )

        # Price development line per day (raw data)
        day_data = df[df['date'] == date]
        if not day_data.empty:
            times = day_data['timestamp']
            raw_prices = day_data['diesel']
            minutes = times.dt.hour * 60 + times.dt.minute
            normalized_x = (minutes - minutes.min()) / (minutes.max() - minutes.min() + 1e-5)
            x_values = bar.get_x() + normalized_x * bar.get_width()

            plt.plot(x_values, raw_prices, color='black', linewidth=1.5)

            # Show only first and last time label
            for i in range(0, len(times)):  # To avoid overlap, show fewer labels
                time_label = times.iloc[i].strftime('%H:%M')
                x = x_values.iloc[i]
                y = raw_prices.iloc[i]
                plt.text(x, y - 0.003, time_label, fontsize=7, ha='center', va='top', rotation=45)

    # Final adjustments
    plt.ylim(1.3, 1.8)
    plt.title(f'Tages-Tiefstpreise Diesel (letzte {len(df_min)} Tage)', pad=20)
    plt.ylabel('€/L')
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.show()

def show_daily_lows():
    df = load_and_prepare_data(DATA_FILE)
    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return

    df_min = prepare_min_price_df(df)
    plot_daily_lows(df, df_min)

if __name__ == '__main__':
    show_daily_lows()
