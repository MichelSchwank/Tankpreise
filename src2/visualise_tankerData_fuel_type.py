"""
Fuel Price Visualization Tool (Multi-Fuel)
===========================================

This module analyzes and visualizes daily fuel prices for diesel, E5, or E10,
highlighting the cheapest times to refuel based on historical price data.

Key Features:
- Supports diesel, E5, and E10 fuel types via command-line argument
- Identifies absolute minimum prices per day
- Calculates "stable minimum" prices (prices that last >=30 minutes)
- Handles late-night and early-morning data by shifting to business hours
- Visualizes price trends throughout the day
- Shows time windows when best prices are available

Author: Michel
Date: 2026-01-08
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta, time, date
from typing import List, Dict, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════


Gasstation = "Tanke_Lud" # gas station to display
Datum = "2026_09_14"# File to look for
SHOW_DAYS = 14 # Number of recent days to display
FUEL_TYPE = "e10" # Fuel type to display: "diesel", "e5", or "e10"

VALID_FUEL_TYPES = ("diesel", "e5", "e10")

# Gasstation must be a key in stations.STATIONS (see that module for the
# full station -> UUID mapping; not needed directly here since this script
# reads an already-filtered per-station file).

# File paths
SCRIPT_DIR = Path(__file__).parent
DATA_FILE = SCRIPT_DIR / f'../data/import/{Datum}_{Gasstation}.csv'

# CSV parsing
SEPARATOR = ','

# Analysis window


# Time boundaries for analysis (business hours)
DAY_START = time(9, 00)   # Start of business day
DAY_END = time(22, 0)    # End of business day

# Time shifting rules for off-hours data
SHIFT_BEFORE = time(8, 0)     # Entries before this time get shifted to 09:00
SHIFT_AFTER_EQ = time(21, 40)  # Entries at/after this time get shifted to next day

# Stable minimum definition
STABLE_MIN_DURATION_MINUTES = 30  # Minimum duration (in minutes) for a price
                                   # to be considered "stable"


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING AND PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def load_and_prepare_data(filepath: Path, fuel_type: str) -> pd.DataFrame:
    """
    Load and preprocess fuel price data from CSV file.

    This function performs several data preparation steps:
    1. Load CSV and parse timestamps
    2. Shift late-night entries (>=22:01) to next day at 00:01
    3. Shift early-morning entries (<08:00) to same day at 09:00
    4. Filter to business hours (09:00-22:00)
    5. Filter to recent days (configured by SHOW_DAYS)
    6. Add synthetic 22:00 entries to "close" each day

    Args:
        filepath: Path to the CSV file containing fuel price data.
                 Expected columns: 'date' (timestamp) and the fuel_type column
        fuel_type: One of 'diesel', 'e5', 'e10'

    Returns:
        DataFrame with columns:
        - timestamp: Parsed datetime
        - price: Fuel price in EUR/L (renamed from the fuel_type column)
        - date: Date component (for grouping)

        Returns empty DataFrame if file not found or data is invalid.
    """
    filepath = Path(filepath)

    # Validate file existence
    if not filepath.exists():
        print(f"Error: File '{filepath}' not found.")
        return pd.DataFrame()

    # Load CSV data
    df = pd.read_csv(filepath, sep=SEPARATOR, engine='python')

    # Validate required columns
    if 'date' not in df.columns:
        print("Error: CSV must contain 'date' column.")
        return pd.DataFrame()

    if fuel_type not in df.columns:
        print(f"Error: CSV must contain '{fuel_type}' column.")
        return pd.DataFrame()

    # Rename fuel column to 'price' for consistent access
    df = df.rename(columns={fuel_type: 'price'})

    # Parse timestamps (dayfirst=True for DD.MM.YYYY format)
    df['timestamp'] = pd.to_datetime(
        df['date'],
        errors='coerce',
        dayfirst=True,
        utc=True
    ).dt.tz_convert('Europe/Berlin').dt.tz_localize(None)

    # Remove rows with invalid timestamps
    df.dropna(subset=['timestamp'], inplace=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Handle late-night entries (>=22:01)
    # ─────────────────────────────────────────────────────────────────────────
    # Strategy: Keep only the latest late-night entry per day and shift it
    #           to 00:01 of the next day
    # Rationale: Late-night prices likely carry over to next morning

    late_mask = df['timestamp'].dt.time >= SHIFT_AFTER_EQ
    if late_mask.any():
        late = df.loc[late_mask].copy()
        late['day'] = late['timestamp'].dt.date

        # Keep only the latest late-night entry per day
        idx_latest_late = late.groupby('day')['timestamp'].idxmax()
        kept_late = late.loc[idx_latest_late].copy()

        # Shift to next day at 00:01
        kept_late['timestamp'] = (
            kept_late['timestamp'].dt.floor('D') + timedelta(days=1, minutes=1)
        )

        # Replace all late-night entries with shifted ones
        df = pd.concat(
            [df.loc[~late_mask].copy(), kept_late.drop(columns=['day'])],
            ignore_index=True
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Handle early-morning entries (<08:00)
    # ─────────────────────────────────────────────────────────────────────────
    # Strategy: Keep only the latest early-morning entry per day and shift it
    #           to 09:00 of the same day
    # Note: This also processes the 00:01 entries from Step 1

    early_mask = df['timestamp'].dt.time < SHIFT_BEFORE
    if early_mask.any():
        early = df.loc[early_mask].copy()
        early['day'] = early['timestamp'].dt.date

        # Keep only the latest early-morning entry per day
        idx_latest_early = early.groupby('day')['timestamp'].idxmax()
        kept_early = early.loc[idx_latest_early].copy()

        # Shift to same day at 09:00
        kept_early['timestamp'] = (
            kept_early['timestamp'].dt.floor('D') + timedelta(hours=9)
        )

        # Replace all early entries with shifted ones
        df = pd.concat(
            [df.loc[~early_mask].copy(), kept_early.drop(columns=['day'])],
            ignore_index=True
        )

    # Sort by timestamp
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Add helper date column for grouping
    df['date'] = df['timestamp'].dt.date

    # ─────────────────────────────────────────────────────────────────────────
    # Filter to business hours (09:00-22:00)
    # ─────────────────────────────────────────────────────────────────────────
    df = df[
        (df['timestamp'].dt.time >= DAY_START) &
        (df['timestamp'].dt.time <= DAY_END)
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # Filter to recent days
    # ─────────────────────────────────────────────────────────────────────────
    cutoff = date.today() - timedelta(days=SHOW_DAYS - 1)
    df = df[df['date'] >= cutoff]

    if df.empty:
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # Add synthetic 22:00 entries
    # ─────────────────────────────────────────────────────────────────────────
    # Purpose: Ensures each day has an endpoint for segment calculation
    #          and visual representation
    # Method: Clone the last price of the day and set timestamp to 22:00

    new_rows = []
    for day, group in df.groupby('date'):
        latest = group.loc[group['timestamp'].idxmax()]

        # Only add synthetic entry if last entry is before 22:00
        if latest['timestamp'].time() < DAY_END:
            clone = latest.copy()
            clone['timestamp'] = datetime.combine(day, DAY_END)
            clone['date'] = day
            new_rows.append(clone)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # Final sort
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# PRICE SEGMENT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def build_price_segments(day_group: pd.DataFrame) -> List[Tuple[datetime, datetime, float]]:
    """
    Convert a day's price observations into piecewise-constant segments.

    A "segment" represents a time period where the price remains constant.
    Each segment lasts from one timestamp until the next timestamp.

    Args:
        day_group: DataFrame containing price data for a single day,
                  with columns 'timestamp' and 'price'

    Returns:
        List of tuples (start_time, end_time, price), where:
        - start_time: Beginning of the price segment
        - end_time: End of the price segment (start of next segment)
        - price: Price during this segment

    Note:
        Returns empty list if fewer than 2 timestamps exist.
        The last timestamp does not create a segment (no known endpoint).
    """
    g = day_group.sort_values('timestamp').reset_index(drop=True)
    segments = []

    # Need at least 2 timestamps to create segments
    if len(g) < 2:
        return segments

    # Create segments from consecutive timestamp pairs
    for i in range(len(g) - 1):
        start = g.loc[i, 'timestamp']
        end = g.loc[i + 1, 'timestamp']
        price = float(g.loc[i, 'price'])

        # Only add valid segments (end after start)
        if end > start:
            segments.append((start, end, price))

    return segments


def get_daily_min_info(
    df: pd.DataFrame,
    stable_duration_minutes: int = STABLE_MIN_DURATION_MINUTES
) -> Dict[date, Dict]:
    """
    Calculate daily minimum prices and identify stable minimum prices.

    For each day, this function computes:
    1. Absolute minimum price (lowest price observed that day)
    2. Stable minimum price (cheapest price that lasts >= stable_duration_minutes)
    3. Time intervals when stable minimum was active

    Args:
        df: DataFrame with fuel price data (output of load_and_prepare_data)
        stable_duration_minutes: Minimum duration (in minutes) for a price
                                to be considered "stable"

    Returns:
        Dictionary mapping each date to:
        {
            'abs_min': float,
            'stable_min': float or None,
            'stable_intervals': [(start_datetime, end_datetime), ...]
        }
    """
    result = {}

    for day, group in df.groupby('date'):
        group = group.sort_values('timestamp')

        # Calculate absolute minimum
        abs_min = float(group['price'].min()) if not group.empty else None

        # Build price segments
        segments = build_price_segments(group)

        # ─────────────────────────────────────────────────────────────────────
        # Merge consecutive segments with same price into intervals
        # ─────────────────────────────────────────────────────────────────────
        intervals_by_price = {}  # price -> [(start, end), ...]

        if segments:
            cur_start, cur_end, cur_price = segments[0]

            for start, end, price in segments[1:]:
                # Check if this segment continues the previous price
                if price == cur_price and start == cur_end:
                    # Extend the current interval
                    cur_end = end
                else:
                    # Save the completed interval and start a new one
                    intervals_by_price.setdefault(cur_price, []).append(
                        (cur_start, cur_end)
                    )
                    cur_start, cur_end, cur_price = start, end, price

            # Don't forget the last interval
            intervals_by_price.setdefault(cur_price, []).append(
                (cur_start, cur_end)
            )

        # ─────────────────────────────────────────────────────────────────────
        # Find stable minimum
        # ─────────────────────────────────────────────────────────────────────
        stable_min = None
        stable_intervals = []

        for price in sorted(intervals_by_price.keys()):
            # Filter intervals by minimum duration
            qualifying = [
                (start, end) for (start, end) in intervals_by_price[price]
                if (end - start).total_seconds() / 60 >= stable_duration_minutes
            ]

            if qualifying:
                # Found the cheapest stable price
                stable_min = float(price)
                stable_intervals = qualifying
                break  # No need to check more expensive prices

        # Store results for this day
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
    """
    Create a complete date range DataFrame, including days with no data.

    Args:
        num_days: Number of days to include (looking back from today)
        daily_info: Dictionary from get_daily_min_info() with price data per day

    Returns:
        DataFrame with columns:
        - date: Date object
        - date_str: Formatted date string for display (DD.MM.YYYY)
        - abs_min: Absolute minimum price (NaN if no data)
        - stable_min: Stable minimum price (NaN if no data)
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days - 1)

    # Generate complete date range
    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    df_complete = pd.DataFrame({
        'date': all_dates.date,
        'date_str': all_dates.strftime('%d.%m.%Y')
    })

    # Map daily info to the complete date range
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
    daily_info: Dict,
    fuel_type: str
) -> None:
    """
    Create a comprehensive visualization of daily minimum fuel prices.

    Args:
        df: Raw price data (output of load_and_prepare_data)
        df_complete: Complete date range with price info
        daily_info: Daily price analysis (output of get_daily_min_info)
        fuel_type: The fuel type being visualized ('diesel', 'e5', 'e10')

    Returns:
        None (displays plot using matplotlib.pyplot.show())
    """
    fuel_label = fuel_type.upper() if fuel_type in ('e5', 'e10') else fuel_type.capitalize()

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(15, 5), dpi=100)

    # X-axis positions (one per day)
    x_positions = list(range(len(df_complete)))
    has_data = df_complete['abs_min'].notna()

    # ──────────────────────────────────────────────────────────────────────────
    # Plot bars for absolute minimum prices
    # ──────────────────────────────────────────────────────────────────────────
    bars = ax.bar(
        [x for x, exists in zip(x_positions, has_data) if exists],
        df_complete.loc[has_data, 'abs_min'],
        color='C0',
        width=0.8,
        label='Tagestiefstpreis'
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Mark missing days
    # ──────────────────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────────────────
    # Add labels and intraday progression for each day
    # ──────────────────────────────────────────────────────────────────────────
    for idx, row in df_complete.iterrows():
        if pd.isna(row['abs_min']):
            continue  # Skip days with no data

        day = row['date']
        x_pos = x_positions[idx]
        abs_price = float(row['abs_min'])
        stable_price = row['stable_min']
        intervals = daily_info.get(day, {}).get('stable_intervals', [])

        # Format time intervals
        interval_text = "\n".join(
            f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
            for start, end in intervals
        )

        # ──────────────────────────────────────────────────────────────────────
        # Build label text
        # ──────────────────────────────────────────────────────────────────────
        label_lines = [f"min: {abs_price:.3f} €"]

        if stable_price is not None and not pd.isna(stable_price):
            if float(stable_price) != abs_price:
                # Stable minimum is higher than absolute minimum
                label_lines.append(
                    f"≥{STABLE_MIN_DURATION_MINUTES}m: {float(stable_price):.3f} €"
                )
                if interval_text:
                    label_lines.append(interval_text)
            else:
                # Stable minimum equals absolute minimum
                if interval_text:
                    label_lines.append(interval_text)

        label = "\n".join(label_lines)

        # Place label inside the bar, anchored at top
        ax.text(
            x_pos,
            abs_price - 0.1,
            label,
            ha='center',
            va='top',
            fontsize=10,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7)
        )

        # ──────────────────────────────────────────────────────────────────────
        # Draw intraday price progression
        # ──────────────────────────────────────────────────────────────────────
        day_data = df[df['date'] == day].sort_values('timestamp')
        if len(day_data) >= 2:
            times = day_data['timestamp']
            raw_prices = day_data['price']

            # Normalize timestamps to fit within bar width
            minutes = times.dt.hour * 60 + times.dt.minute
            denom = (minutes.max() - minutes.min()) or 1
            normalized = (minutes - minutes.min()) / denom
            x_values = x_pos - 0.4 + normalized * 0.8  # Scale to bar width

            # Draw step plot
            ax.step(
                x_values,
                raw_prices,
                where='post',  # Price stays constant until next timestamp
                color='black',
                linewidth=1.5
            )

            # Add time labels at each price change
            for x, y, t in zip(x_values, raw_prices, times.dt.strftime('%H:%M')):
                ax.text(
                    x,
                    y - 0.003,
                    t,
                    fontsize=7,
                    ha='center',
                    va='top',
                    rotation=45
                )

    # ──────────────────────────────────────────────────────────────────────────
    # Format axes and labels
    # ──────────────────────────────────────────────────────────────────────────
    ax.set_ylim(1.3, 2.5)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(df_complete['date_str'], rotation=45, ha='right')
    ax.set_ylabel('Preis (€/L)', fontsize=12)
    ax.set_title(
        f'Tages-Tiefstpreise {fuel_label}\n'
        f'(letzte {SHOW_DAYS} Tage, {has_data.sum()} mit Daten)',
        pad=20,
        fontsize=14,
        fontweight='bold'
    )
    ax.grid(axis='y', linestyle='--', alpha=0.4)

    # Add legend if there are missing days
    if missing_positions:
        ax.legend(loc='upper right')

    plt.tight_layout()
    plt.show()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Main execution function.

    Usage:
        python visualise_tankerData_e5.py [diesel|e5|e10]

    Defaults to 'diesel' if no argument is provided.
    """
    # Parse fuel type from command-line arguments
    if len(sys.argv) > 1:
        fuel_type = sys.argv[1].lower()
    else:
        fuel_type = FUEL_TYPE

    if fuel_type not in VALID_FUEL_TYPES:
        print(f"Error: Invalid fuel type '{fuel_type}'. Must be one of: {', '.join(VALID_FUEL_TYPES)}")
        sys.exit(1)

    fuel_label = fuel_type.upper() if fuel_type in ('e5', 'e10') else fuel_type.capitalize()

    print(f"Loading {fuel_label} price data from: {DATA_FILE}")
    print(f"Analyzing last {SHOW_DAYS} days...")
    print(f"Stable minimum threshold: {STABLE_MIN_DURATION_MINUTES} minutes\n")

    # Load data
    df = load_and_prepare_data(DATA_FILE, fuel_type)
    if df.empty:
        print("Error: No valid data found in file.")
        return

    print(f"Loaded {len(df)} price observations")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}\n")

    # Analyze daily minimums
    daily_info = get_daily_min_info(df, stable_duration_minutes=STABLE_MIN_DURATION_MINUTES)

    # Create complete date range
    df_complete = create_complete_date_range(SHOW_DAYS, daily_info)

    # Generate visualization
    print("Generating visualization...")
    avg_min = df_complete['abs_min'].mean()
    print(f"Average minimum {fuel_label} price ({df_complete['abs_min'].notna().sum()} days with data): {avg_min:.3f} €/L")
    plot_daily_lows(df, df_complete, daily_info, fuel_type)
    print("Done!")


if __name__ == '__main__':
    main()
