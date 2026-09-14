"""
Processed Fuel Price Visualization Tool (Long-term)
=====================================================

This module analyzes and visualizes daily diesel fuel prices from processed
data sources, highlighting optimal refueling times based on historical patterns.

This version is designed for pre-processed CSV data files with semicolon separators.
It identifies both absolute minimum prices and "stable minimum" prices (prices
lasting at least 30 minutes), helping users find the best times to refuel.

Key Features:
- Processes data with semicolon-delimited CSV format
- Identifies absolute minimum prices per day
- Calculates "stable minimum" prices (prices lasting ≥30 minutes)
- Handles late-night and early-morning data by shifting to business hours
- Visualizes intraday price trends with step plots
- Handles missing data gracefully with visual indicators

Author: Michel
Date: 2026-01-08
Version: 1.0
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta, time, date
from typing import List, Dict, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

SHOW_DAYS = 148
min_price = 1.3
max_price = 2.4
DAY_START = time(9, 0)   # Start of business day
DAY_END = time(22, 0)    # End of business day
SHIFT_BEFORE = time(9, 0)     # Entries before this time get shifted to 09:00
SHIFT_AFTER_EQ = time(21, 40)  # Entries at/after this time get shifted to next day
STABLE_MIN_DURATION_MINUTES = 30  # Minimum duration (in minutes) for a price
                                   # to be considered "stable"
FUEL_TYPE = "e5"  # One of "diesel", "e5", "e10"
STATION = "Tanke_Lud"  # Which station's rows to pick out of the shared CSV files

# File paths
SCRIPT_DIR = Path(__file__).parent
_FUEL_FILES = {
    "diesel": SCRIPT_DIR / '../data/processed/diesel_prices_3.csv',
    "e5":     SCRIPT_DIR / '../data/processed/e5_prices_1.csv',
    "e10":    SCRIPT_DIR / '../data/processed/e10_prices_1.csv',
}
DATA_FILE = _FUEL_FILES[FUEL_TYPE]
SEPARATOR = ';'# CSV parsing

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING AND PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def load_and_prepare_data(filepath: Path) -> pd.DataFrame:
    filepath = Path(filepath)

    if not filepath.exists():
        print(f"Error: File '{filepath}' not found.")
        print(f"Expected location: {filepath.absolute()}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(filepath, sep=SEPARATOR, engine='python')
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return pd.DataFrame()

    if 'date' not in df.columns:
        print("Error: CSV must contain 'date' column.")
        print(f"Available columns: {', '.join(df.columns)}")
        return pd.DataFrame()

    if FUEL_TYPE not in df.columns:
        print(f"Error: CSV must contain '{FUEL_TYPE}' column.")
        print(f"Available columns: {', '.join(df.columns)}")
        return pd.DataFrame()

    # The CSV holds rows for multiple stations. Rows written before
    # multi-station support existed have no 'station' column and are all
    # implicitly Tanke_Lud, so only filter when the column is present.
    if 'station' in df.columns:
        df = df[df['station'] == STATION].copy()
        if df.empty:
            print(f"Error: No rows found for station '{STATION}'.")
            return df

    df['timestamp'] = pd.to_datetime(
        df['date'],
        format='%Y-%m-%d %H:%M:%S',
        errors='coerce'
    ).dt.tz_localize(None)

    initial_count = len(df)
    df.dropna(subset=['timestamp'], inplace=True)
    if len(df) < initial_count:
        print(f"Warning: Removed {initial_count - len(df)} rows with invalid timestamps")

    if df.empty:
        print("Error: No valid timestamps found in data")
        return df

    late_mask = df['timestamp'].dt.time >= SHIFT_AFTER_EQ
    if late_mask.any():
        late = df.loc[late_mask].copy()
        late['day'] = late['timestamp'].dt.date

        idx_latest_late = late.groupby('day')['timestamp'].idxmax()
        kept_late = late.loc[idx_latest_late].copy()

        kept_late['timestamp'] = (
            kept_late['timestamp'].dt.floor('D') + timedelta(days=1, minutes=1)
        )

        df = pd.concat(
            [df.loc[~late_mask].copy(), kept_late.drop(columns=['day'])],
            ignore_index=True
        )

    early_mask = df['timestamp'].dt.time < SHIFT_BEFORE
    if early_mask.any():
        early = df.loc[early_mask].copy()
        early['day'] = early['timestamp'].dt.date

        idx_latest_early = early.groupby('day')['timestamp'].idxmax()
        kept_early = early.loc[idx_latest_early].copy()

        kept_early['timestamp'] = (
            kept_early['timestamp'].dt.floor('D') + timedelta(hours=9)
        )

        df = pd.concat(
            [df.loc[~early_mask].copy(), kept_early.drop(columns=['day'])],
            ignore_index=True
        )

    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    df['date'] = df['timestamp'].dt.date

    df = df[
        (df['timestamp'].dt.time >= DAY_START) &
        (df['timestamp'].dt.time <= DAY_END)
    ]

    cutoff = date.today() - timedelta(days=SHOW_DAYS - 1)
    df = df[df['date'] >= cutoff]

    if df.empty:
        print(f"Warning: No data found in last {SHOW_DAYS} days")
        return df

    new_rows = []
    for day, group in df.groupby('date'):
        latest = group.loc[group['timestamp'].idxmax()]

        if latest['timestamp'].time() < DAY_END:
            clone = latest.copy()
            clone['timestamp'] = datetime.combine(day, DAY_END)
            clone['date'] = day
            new_rows.append(clone)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# PRICE SEGMENT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def build_price_segments(day_group: pd.DataFrame) -> List[Tuple[datetime, datetime, float]]:
    g = day_group.sort_values('timestamp').reset_index(drop=True)
    segments = []

    if len(g) < 2:
        return segments

    for i in range(len(g) - 1):
        start = g.loc[i, 'timestamp']
        end = g.loc[i + 1, 'timestamp']
        price = float(g.loc[i, FUEL_TYPE])

        if end > start:
            segments.append((start, end, price))

    return segments


def get_daily_min_info(
    df: pd.DataFrame,
    stable_duration_minutes: int = STABLE_MIN_DURATION_MINUTES
) -> Dict[date, Dict]:
    result = {}

    for day, group in df.groupby('date'):
        group = group.sort_values('timestamp')

        abs_min = float(group[FUEL_TYPE].min()) if not group.empty else None

        segments = build_price_segments(group)

        intervals_by_price = {}

        if segments:
            cur_start, cur_end, cur_price = segments[0]

            for start, end, price in segments[1:]:
                if price == cur_price and start == cur_end:
                    cur_end = end
                else:
                    intervals_by_price.setdefault(cur_price, []).append(
                        (cur_start, cur_end)
                    )
                    cur_start, cur_end, cur_price = start, end, price

            intervals_by_price.setdefault(cur_price, []).append(
                (cur_start, cur_end)
            )

        stable_min = None
        stable_intervals = []

        for price in sorted(intervals_by_price.keys()):
            qualifying = [
                (start, end) for (start, end) in intervals_by_price[price]
                if (end - start).total_seconds() / 60 >= stable_duration_minutes
            ]

            if qualifying:
                stable_min = float(price)
                stable_intervals = qualifying
                break

        result[day] = {
            'abs_min': abs_min,
            'stable_min': stable_min,
            'stable_intervals': stable_intervals,
        }

    return result


# ══════════════════════════════════════════════════════════════════════════════
# DATE RANGE HANDLING
# ══════════════════════════════════════════════════════════════════════════════

def create_complete_date_range(num_days: int, daily_info: Dict) -> pd.DataFrame:
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days - 1)

    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')

    df_complete = pd.DataFrame({
        'date': all_dates.date,
        'date_str': all_dates.strftime('%d.%m.%Y')
    })

    df_complete['abs_min'] = df_complete['date'].map(
        lambda d: daily_info.get(d, {}).get('abs_min')
    )
    df_complete['stable_min'] = df_complete['date'].map(
        lambda d: daily_info.get(d, {}).get('stable_min')
    )

    return df_complete


# ══════════════════════════════════════════════════════════════════════════════
# VISUALIZATION
# ══════════════════════════════════════════════════════════════════════════════

def plot_daily_lows(
    df: pd.DataFrame,
    df_complete: pd.DataFrame,
    daily_info: Dict
) -> None:
    fig, ax = plt.subplots(figsize=(15, 5), dpi=100)

    x_positions = list(range(len(df_complete)))
    has_data = df_complete['abs_min'].notna()

    bars = ax.bar(
        [x for x, exists in zip(x_positions, has_data) if exists],
        df_complete.loc[has_data, 'abs_min'],
        color='C0',
        width=0.8,
        label='Tagestiefstpreis',
        zorder=2
    )

    missing_positions = [x for x, exists in zip(x_positions, has_data) if not exists]
    if missing_positions:
        ax.scatter(
            missing_positions,
            [1.55] * len(missing_positions),
            marker='x',
            s=100,
            color='lightgray',
            alpha=0.5,
            label='Keine Daten',
            zorder=3
        )

    ax.set_ylim(min_price, max_price)
    ax.set_xticks(x_positions[::2])
    ax.set_xticklabels(df_complete['date_str'].iloc[::2], rotation=45, ha='right')
    ax.set_ylabel('Preis (€/L)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Datum', fontsize=12, fontweight='bold')
    fuel_label = FUEL_TYPE.upper() if FUEL_TYPE in ('e5', 'e10') else FUEL_TYPE.capitalize()
    ax.set_title(
        f'Tages-Tiefstpreise {fuel_label}\n'
        f'(letzte {SHOW_DAYS} Tage, {has_data.sum()} Tage mit Daten)',
        pad=20,
        fontsize=14,
        fontweight='bold'
    )
    ax.grid(axis='y', linestyle='--', alpha=0.3, zorder=1)

    if missing_positions:
        ax.legend(loc='upper right', fontsize=10)

    plt.tight_layout()
    plt.show()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 70)
    print("Fuel Price Visualization Tool - Processed Data (Long-term)")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Data file: {DATA_FILE}")
    print(f"  Analysis window: Last {SHOW_DAYS} days")
    print(f"  Stable minimum threshold: {STABLE_MIN_DURATION_MINUTES} minutes")
    print(f"  Business hours: {DAY_START.strftime('%H:%M')} - {DAY_END.strftime('%H:%M')}")
    print("\n" + "-" * 70)

    print("\nLoading data...")
    df = load_and_prepare_data(DATA_FILE)

    if df.empty:
        print("\n[ERROR] No valid data found.")
        print("        Please check that the file exists and contains valid data.")
        return

    print(f"[OK] Loaded {len(df)} price observations")
    print(f"[OK] Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"[OK] Unique days: {df['date'].nunique()}")

    print("\nAnalyzing daily minimum prices...")
    daily_info = get_daily_min_info(
        df,
        stable_duration_minutes=STABLE_MIN_DURATION_MINUTES
    )

    print("Creating complete date range...")
    df_complete = create_complete_date_range(SHOW_DAYS, daily_info)

    print("Generating visualization...")
    print("\n" + "=" * 70)
    plot_daily_lows(df, df_complete, daily_info)

    print("\n[OK] Done! Close the plot window to exit.")


if __name__ == '__main__':
    main()
