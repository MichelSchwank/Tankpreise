import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta, time, date

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
# Use path relative to this script file, not working directory
SCRIPT_DIR = Path(__file__).parent
DATA_FILE =  SCRIPT_DIR / '../../data/raw/2026_01_07_Lud.csv'
#SCRIPT_DIR / '../data/processed/diesel_prices_3.csv'   # CSV file path
MAX_GAP_MINUTES = 600                  # Max gap between identical prices in minutes
MIN_GAP_MINUTES = 50                   # Min duration for a gap to be displayed
SEPERATOR = ','
show_days = 3


# ──────────────────────────────────────────────────────────────────────────────
# 1. Load and preprocess data
# ──────────────────────────────────────────────────────────────────────────────
def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    """y
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
def get_daily_min_intervals(df: pd.DataFrame, min_duration_minutes=MIN_GAP_MINUTES) -> dict:
    """
    Return a dict of {date: [(start, end), ...]} intervals when a qualifying price was active.
    Returns intervals for the cheapest price that has at least one interval >= min_duration_minutes.
    """
    result = {}
    for day, group in df.groupby('date'):
        # Get all unique prices sorted from cheapest to most expensive
        unique_prices = sorted(group['diesel'].unique())

        # Collect all qualifying intervals from all price levels
        all_qualifying_intervals = []

        for price in unique_prices:
            timestamps = group[group['diesel'] == price]['timestamp'].sort_values()
            if not timestamps.empty:
                intervals = group_close_timestamps(timestamps.tolist())
                # Filter intervals that meet minimum duration
                filtered_intervals = [
                    (start, end) for start, end in intervals
                    if (end - start).total_seconds() / 60 >= min_duration_minutes
                ]
                if filtered_intervals:
                    # Store price with its qualifying intervals
                    all_qualifying_intervals.append((price, filtered_intervals))

        # If we found any qualifying intervals, use the cheapest price's intervals
        if all_qualifying_intervals:
            # all_qualifying_intervals is already sorted by price (cheapest first)
            cheapest_price, intervals = all_qualifying_intervals[0]
            result[day] = intervals
        else:
            result[day] = []

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 4. Create complete date range with gaps for missing days
# ──────────────────────────────────────────────────────────────────────────────
def create_complete_date_range(df: pd.DataFrame, num_days: int) -> pd.DataFrame:
    """
    Create a complete date range DataFrame with NaN prices for missing days.
    This ensures all days in the lookback period are represented, even if no data exists.
    """
    if df.empty:
        return df

    # Generate complete date range
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days - 1)

    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    complete_df = pd.DataFrame({
        'date': all_dates.date,
        'date_str': all_dates.strftime('%d.%m.%Y')
    })

    # Get minimum prices per day from actual data
    if not df.empty:
        idx_min = df.groupby('date')['diesel'].idxmin()
        min_df = df.loc[idx_min, ['date', 'diesel', 'timestamp']].copy()

        # Merge with complete date range (left join to keep all dates)
        complete_df = complete_df.merge(min_df, on='date', how='left')
    else:
        complete_df['diesel'] = None
        complete_df['timestamp'] = None

    return complete_df


# ──────────────────────────────────────────────────────────────────────────────
# 5. Visualize daily minimum diesel prices with gaps
# ──────────────────────────────────────────────────────────────────────────────
def plot_daily_lows(df: pd.DataFrame, df_complete: pd.DataFrame, interval_dict: dict):
    """
    Create a bar plot of daily minimum diesel prices with gaps for missing days.
    Shows all days in the time range, with empty spaces where data is missing.
    Displays time intervals when minimum prices were active.
    """
    fig, ax = plt.subplots(figsize=(15, 5), dpi=100)

    # Create x-axis positions for all dates
    x_positions = range(len(df_complete))

    # Separate data into existing and missing
    has_data = df_complete['diesel'].notna()

    # Plot bars only for days with data
    bars = ax.bar(
        [x for x, exists in zip(x_positions, has_data) if exists],
        df_complete.loc[has_data, 'diesel'],
        color='C0',
        width=0.8
    )

    # Add faint markers for missing days
    missing_positions = [x for x, exists in zip(x_positions, has_data) if not exists]
    if missing_positions:
        ax.scatter(
            missing_positions,
            [1.55] * len(missing_positions),  # Middle of y-axis
            marker='x',
            s=100,
            color='lightgray',
            alpha=0.5,
            label='Keine Daten'
        )

    # Annotate bars with prices and intraday progression
    bar_idx = 0
    for idx, row in df_complete.iterrows():
        if pd.isna(row['diesel']):
            continue

        bar = bars[bar_idx]
        price = row['diesel']
        day = row['date']
        x_pos = x_positions[idx]

        # Get time intervals when minimum price was active
        intervals = interval_dict.get(day, [])
        interval_text = "\n".join(f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
                                  for start, end in intervals)

        # Price label with intervals
        label = f"{price:.3f} €"
        if interval_text:
            label += f"\n{interval_text}"

        ax.text(x_pos, price - 0.05,
                label,
                ha='center', va='center', fontsize=10)

        # Step plot for price progression
        day_data = df[df['date'] == day].sort_values('timestamp')
        if not day_data.empty:
            times = day_data['timestamp']
            raw_prices = day_data['diesel']
            minutes = times.dt.hour * 60 + times.dt.minute
            normalized = (minutes - minutes.min()) / (minutes.max() - minutes.min() + 1e-5)
            x_values = x_pos - 0.4 + normalized * 0.8  # Scale to bar width

            ax.step(x_values, raw_prices, where='post', color='black', linewidth=1.5)

            # Time labels
            for x, y, t in zip(x_values, raw_prices, times.dt.strftime('%H:%M')):
                ax.text(x, y - 0.003, t, fontsize=7, ha='center', va='top', rotation=45)

        bar_idx += 1

    # Formatting
    ax.set_ylim(1.3, 1.8)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(df_complete['date_str'], rotation=45, ha='right')
    ax.set_ylabel('€/L')
    ax.set_title(
        f'Tages-Tiefstpreise Diesel (letzte {show_days} Tage, {has_data.sum()} mit Daten)',
        pad=20
    )
    ax.grid(axis='y', linestyle='--', alpha=0.4)

    if missing_positions:
        ax.legend(loc='upper right')

    plt.tight_layout()
    plt.show()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Main entry point
# ──────────────────────────────────────────────────────────────────────────────
def show_daily_lows():
    """
    Load data, compute daily minimums with gaps, and show the annotated plot.
    """
    df = load_and_prepare_data(DATA_FILE)
    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return

    # Create complete date range including gaps
    df_complete = create_complete_date_range(df, show_days)

    # Calculate intervals when minimum price was active (with min duration filter)
    interval_dict = get_daily_min_intervals(df)

    # Plot with interval information
    plot_daily_lows(df, df_complete, interval_dict)


if __name__ == '__main__':
    show_daily_lows()
