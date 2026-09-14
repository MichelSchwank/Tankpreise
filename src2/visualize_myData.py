"""
Processed Fuel Price Visualization Tool
========================================

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
- Shows time windows when best prices are available
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

SHOW_DAYS = 14
min_price = 1.3
max_price = 2.4
DAY_START = time(9, 0)   # Start of business day
DAY_END = time(22, 0)    # End of business day
SHIFT_BEFORE = time(9, 0)     # Entries before this time get shifted to 09:00
SHIFT_AFTER_EQ = time(21, 40)  # Entries at/after this time get shifted to next day
STABLE_MIN_DURATION_MINUTES = 30  # Minimum duration (in minutes) for a price
                                   # to be considered "stable"
FUEL_TYPE = "e10"  # One of "diesel", "e5", "e10"
STATION = "Tanke_Lud"  # Which station's rows to pick out of the shared CSV files

# File paths
SCRIPT_DIR = Path(__file__).parent
_FUEL_FILES = {
    "diesel": SCRIPT_DIR / '../data/log/diesel_prices_3.csv',
    "e5":     SCRIPT_DIR / '../data/log/e5_prices_1.csv',
    "e10":    SCRIPT_DIR / '../data/log/e10_prices_1.csv',
}
DATA_FILE = _FUEL_FILES[FUEL_TYPE]
SEPARATOR = ';'# CSV parsing

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING AND PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def load_and_prepare_data(filepath: Path) -> pd.DataFrame:
    """
    Load and preprocess fuel price data from semicolon-delimited CSV file.

    This function performs comprehensive data preparation:
    1. Load CSV with semicolon separator
    2. Parse timestamps with day-first format (DD.MM.YYYY)
    3. Normalize late-night entries (≥22:01) to next day at 00:01
    4. Normalize early-morning entries (<08:00) to same day at 09:00
    5. Filter to business hours (09:00-22:00)
    6. Filter to recent days (configurable window)
    7. Add synthetic 22:00 entries to complete each day

    Data Normalization Strategy:
    ───────────────────────────
    Late-night prices (≥22:01):
        - Keep only the latest observation per day
        - Shift to 00:01 of next day
        - Rationale: Late prices likely represent overnight carryover

    Early-morning prices (<09:00):
        - Keep only the latest observation per day
        - Shift to 09:00 of same day
        - Rationale: Opening price represents morning availability

    Args:
        filepath: Path to semicolon-delimited CSV file.
                 Required columns: 'date' (timestamp), 'diesel' (price in EUR/L)

    Returns:
        DataFrame with columns:
        - timestamp: Parsed datetime object (timezone-naive)
        - diesel: Fuel price in EUR per liter
        - date: Date component extracted for grouping operations

        Returns empty DataFrame if:
        - File not found
        - Required columns missing
        - No valid data after filtering

    Example CSV Format:
        date;diesel
        07.01.2026 09:30;1.549
        07.01.2026 14:25;1.539
        07.01.2026 18:15;1.545

    Note:
        Synthetic 22:00 entries ensure each day has a defined endpoint
        for segment calculation and visual representation.
    """
    filepath = Path(filepath)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Validate file existence
    # ─────────────────────────────────────────────────────────────────────────
    if not filepath.exists():
        print(f"Error: File '{filepath}' not found.")
        print(f"Expected location: {filepath.absolute()}")
        return pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Load CSV data
    # ─────────────────────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(filepath, sep=SEPARATOR, engine='python')
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Validate required columns
    # ─────────────────────────────────────────────────────────────────────────
    if 'date' not in df.columns:
        print("Error: CSV must contain 'date' column.")
        print(f"Available columns: {', '.join(df.columns)}")
        return pd.DataFrame()

    if FUEL_TYPE not in df.columns:
        print(f"Error: CSV must contain '{FUEL_TYPE}' column.")
        print(f"Available columns: {', '.join(df.columns)}")
        return pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3b: Filter to the configured station
    # ─────────────────────────────────────────────────────────────────────────
    # The CSV holds rows for multiple stations. Rows written before
    # multi-station support existed have no 'station' column and are all
    # implicitly Tanke_Lud, so only filter when the column is present.
    if 'station' in df.columns:
        df = df[df['station'] == STATION].copy()
        if df.empty:
            print(f"Error: No rows found for station '{STATION}'.")
            return df

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Parse timestamps
    # ─────────────────────────────────────────────────────────────────────────
    # Parse timestamps in YYYY-MM-DD HH:MM:SS format
    df['timestamp'] = pd.to_datetime(
        df['date'],
        format='%Y-%m-%d %H:%M:%S',
        errors='coerce'
    ).dt.tz_localize(None)

    # Remove rows with unparseable timestamps
    initial_count = len(df)
    df.dropna(subset=['timestamp'], inplace=True)
    if len(df) < initial_count:
        print(f"Warning: Removed {initial_count - len(df)} rows with invalid timestamps")

    if df.empty:
        print("Error: No valid timestamps found in data")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Normalize late-night entries (≥22:01)
    # ─────────────────────────────────────────────────────────────────────────
    # Strategy: Keep only latest late-night entry per day, shift to next day
    late_mask = df['timestamp'].dt.time >= SHIFT_AFTER_EQ
    if late_mask.any():
        late = df.loc[late_mask].copy()
        late['day'] = late['timestamp'].dt.date

        # Keep only the latest late-night observation per day
        idx_latest_late = late.groupby('day')['timestamp'].idxmax()
        kept_late = late.loc[idx_latest_late].copy()

        # Shift to 00:01 of next day
        kept_late['timestamp'] = (
            kept_late['timestamp'].dt.floor('D') + timedelta(days=1, minutes=1)
        )

        # Replace all late-night entries with shifted ones
        df = pd.concat(
            [df.loc[~late_mask].copy(), kept_late.drop(columns=['day'])],
            ignore_index=True
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Normalize early-morning entries (<08:00)
    # ─────────────────────────────────────────────────────────────────────────
    # Strategy: Keep only latest early entry per day, shift to 09:00 same day
    # Note: This also processes the 00:01 entries created in Step 5
    early_mask = df['timestamp'].dt.time < SHIFT_BEFORE
    if early_mask.any():
        early = df.loc[early_mask].copy()
        early['day'] = early['timestamp'].dt.date

        # Keep only the latest early-morning observation per day
        idx_latest_early = early.groupby('day')['timestamp'].idxmax()
        kept_early = early.loc[idx_latest_early].copy()

        # Shift to 09:00 of same day
        kept_early['timestamp'] = (
            kept_early['timestamp'].dt.floor('D') + timedelta(hours=9)
        )

        # Replace all early entries with shifted ones
        df = pd.concat(
            [df.loc[~early_mask].copy(), kept_early.drop(columns=['day'])],
            ignore_index=True
        )

    # Sort chronologically
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Add helper date column
    # ─────────────────────────────────────────────────────────────────────────
    df['date'] = df['timestamp'].dt.date

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Filter to business hours
    # ─────────────────────────────────────────────────────────────────────────
    df = df[
        (df['timestamp'].dt.time >= DAY_START) &
        (df['timestamp'].dt.time <= DAY_END)
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: Filter to recent days
    # ─────────────────────────────────────────────────────────────────────────
    cutoff = date.today() - timedelta(days=SHOW_DAYS - 1)
    df = df[df['date'] >= cutoff]

    if df.empty:
        print(f"Warning: No data found in last {SHOW_DAYS} days")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # Step 10: Add synthetic 22:00 entries
    # ─────────────────────────────────────────────────────────────────────────
    # Purpose: Ensures each day has a defined endpoint for:
    #   - Segment duration calculations
    #   - Visual representation in plots
    # Method: Clone last known price of day and set time to 22:00
    new_rows = []
    for day, group in df.groupby('date'):
        latest = group.loc[group['timestamp'].idxmax()]

        # Only add if last entry is before 22:00
        if latest['timestamp'].time() < DAY_END:
            clone = latest.copy()
            clone['timestamp'] = datetime.combine(day, DAY_END)
            clone['date'] = day
            new_rows.append(clone)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # Final sort and index reset
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# PRICE SEGMENT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def build_price_segments(day_group: pd.DataFrame) -> List[Tuple[datetime, datetime, float]]:
    """
    Convert daily price observations into piecewise-constant time segments.

    A "segment" represents a continuous time period where the price remains
    constant. Each segment spans from one timestamp to the next timestamp.
    This representation is essential for calculating how long each price
    was actually available to customers.

    Args:
        day_group: DataFrame containing all price observations for a single day.
                  Must have 'timestamp' and 'diesel' columns.

    Returns:
        List of tuples (start_time, end_time, price), where:
        - start_time: Beginning timestamp of constant-price segment
        - end_time: Ending timestamp (when price changes)
        - price: Price (EUR/L) during this segment

        Returns empty list if fewer than 2 timestamps exist.

    Segment Logic:
        Given timestamps T1, T2, T3 with prices P1, P2, P3:
        - Segment 1: (T1, T2, P1) - P1 valid from T1 until T2
        - Segment 2: (T2, T3, P2) - P2 valid from T2 until T3
        - No segment for T3 (no known endpoint)

    Example:
        Input:  09:00 → €1.55
                14:00 → €1.53
                18:00 → €1.54
                22:00 → €1.54

        Output: [(09:00, 14:00, 1.55),  # 5 hours at €1.55
                 (14:00, 18:00, 1.53),  # 4 hours at €1.53
                 (18:00, 22:00, 1.54)]  # 4 hours at €1.54

    Note:
        The last timestamp doesn't create a segment because we don't know
        when it ends. The synthetic 22:00 entry (added in preprocessing)
        ensures the last real observation has a defined endpoint.
    """
    g = day_group.sort_values('timestamp').reset_index(drop=True)
    segments = []

    # Need at least 2 timestamps to define a segment
    if len(g) < 2:
        return segments

    # Create segments from consecutive timestamp pairs
    for i in range(len(g) - 1):
        start = g.loc[i, 'timestamp']
        end = g.loc[i + 1, 'timestamp']
        price = float(g.loc[i, FUEL_TYPE])

        # Only include valid segments (end after start)
        if end > start:
            segments.append((start, end, price))

    return segments


def get_daily_min_info(
    df: pd.DataFrame,
    stable_duration_minutes: int = STABLE_MIN_DURATION_MINUTES
) -> Dict[date, Dict]:
    """
    Calculate comprehensive daily minimum price information.

    For each day, computes three key metrics:
    1. Absolute minimum price (lowest price observed, regardless of duration)
    2. Stable minimum price (cheapest price lasting ≥ threshold duration)
    3. Time intervals when stable minimum was active

    The "stable minimum" is crucial for practical refueling decisions because
    a price that only lasts a few minutes may not be actionable. This function
    identifies the cheapest price that was available long enough to be useful.

    Args:
        df: DataFrame with preprocessed fuel price data
           (output of load_and_prepare_data)
        stable_duration_minutes: Minimum duration (minutes) for a price
                                to be considered "stable"

    Returns:
        Dictionary mapping each date to a dictionary with:
        {
            'abs_min': float,               # Absolute minimum price (EUR/L)
            'stable_min': float or None,    # Stable minimum price (EUR/L)
            'stable_intervals': [            # Time windows for stable minimum
                (start_datetime, end_datetime),
                (start_datetime, end_datetime),
                ...
            ]
        }

        'stable_min' is None if no price lasted ≥ threshold duration
        'stable_intervals' is empty list if no stable minimum exists

    Algorithm Details:
        Step 1: Build price segments for the day
                (periods where price remained constant)

        Step 2: Merge consecutive segments with same price
                (combine adjacent periods with identical prices)

        Step 3: Find cheapest price with intervals ≥ threshold
                (iterate prices from cheapest to most expensive,
                 return first one with qualifying duration)

    Example Scenario:
        Day's prices:
        - €1.53 from 09:00-09:20 (20 min) ← too short!
        - €1.54 from 10:00-14:00 (4 hours) ← stable ✓
        - €1.55 from 14:00-22:00 (8 hours)

        Result with 30-minute threshold:
        - abs_min: 1.53 (absolute lowest)
        - stable_min: 1.54 (cheapest price lasting ≥30 min)
        - stable_intervals: [(10:00, 14:00)]

    Note:
        If multiple non-consecutive intervals exist for the stable minimum price,
        all qualifying intervals are included in 'stable_intervals'.
    """
    result = {}

    for day, group in df.groupby('date'):
        group = group.sort_values('timestamp')

        # ─────────────────────────────────────────────────────────────────────
        # Calculate absolute minimum (simple minimum regardless of duration)
        # ─────────────────────────────────────────────────────────────────────
        abs_min = float(group[FUEL_TYPE].min()) if not group.empty else None

        # ─────────────────────────────────────────────────────────────────────
        # Build price segments
        # ─────────────────────────────────────────────────────────────────────
        segments = build_price_segments(group)

        # ─────────────────────────────────────────────────────────────────────
        # Merge consecutive segments with identical prices
        # ─────────────────────────────────────────────────────────────────────
        # Purpose: If price stayed constant across multiple observations,
        #          combine into single continuous interval for accurate duration
        intervals_by_price = {}  # Maps: price → [(start, end), ...]

        if segments:
            # Initialize with first segment
            cur_start, cur_end, cur_price = segments[0]

            # Process remaining segments
            for start, end, price in segments[1:]:
                # Check if this segment continues the previous price
                if price == cur_price and start == cur_end:
                    # Extend current interval (same price continues)
                    cur_end = end
                else:
                    # Price changed: save completed interval, start new one
                    intervals_by_price.setdefault(cur_price, []).append(
                        (cur_start, cur_end)
                    )
                    cur_start, cur_end, cur_price = start, end, price

            # Don't forget the final interval
            intervals_by_price.setdefault(cur_price, []).append(
                (cur_start, cur_end)
            )

        # ─────────────────────────────────────────────────────────────────────
        # Find stable minimum price
        # ─────────────────────────────────────────────────────────────────────
        # Strategy: Iterate prices from cheapest to most expensive
        #           Return first price with intervals ≥ minimum duration
        stable_min = None
        stable_intervals = []

        for price in sorted(intervals_by_price.keys()):
            # Filter intervals by minimum duration requirement
            qualifying = [
                (start, end) for (start, end) in intervals_by_price[price]
                if (end - start).total_seconds() / 60 >= stable_duration_minutes
            ]

            if qualifying:
                # Found cheapest price with sufficient duration
                stable_min = float(price)
                stable_intervals = qualifying
                break  # No need to check more expensive prices

        # ─────────────────────────────────────────────────────────────────────
        # Store results for this day
        # ─────────────────────────────────────────────────────────────────────
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
    Create complete date range DataFrame, including days with missing data.

    This ensures the visualization displays all days in the analysis window,
    even when some days have no price data (e.g., station closed, data gap,
    system downtime). Missing days are shown with visual indicators.

    Args:
        num_days: Number of consecutive days to include
                 (counting back from today)
        daily_info: Dictionary from get_daily_min_info() containing
                   price analysis results per day

    Returns:
        DataFrame with columns:
        - date: Python date object
        - date_str: Formatted date string for display (DD.MM.YYYY)
        - abs_min: Absolute minimum price (NaN if no data available)
        - stable_min: Stable minimum price (NaN if no data available)

    Example:
        If today is January 8 and num_days=7:
        Result includes: Jan 2, 3, 4, 5, 6, 7, 8
        - Days with data: abs_min and stable_min populated
        - Days without data: NaN values (shown as gaps in visualization)

    Note:
        This approach ensures the x-axis spacing is uniform and missing
        days are visually apparent to the user.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days - 1)

    # Generate complete date range (no gaps)
    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')

    # Create base DataFrame with all dates
    df_complete = pd.DataFrame({
        'date': all_dates.date,
        'date_str': all_dates.strftime('%d.%m.%Y')
    })

    # Map daily price info to complete date range
    # (missing days will have NaN values)
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
    """
    Create comprehensive visualization of daily minimum fuel prices.

    Generates a multi-layered plot showing:
    - Bar chart: Absolute minimum price per day (bar height)
    - Step plot: Intraday price progression (black line)
    - Text labels: Prices and optimal refueling time windows
    - Gap markers: Visual indicators for missing data days

    Args:
        df: Raw preprocessed price data
           (output of load_and_prepare_data)
        df_complete: Complete date range with daily price summary
                    (output of create_complete_date_range)
        daily_info: Detailed daily price analysis
                   (output of get_daily_min_info)

    Returns:
        None (displays interactive plot via matplotlib)

    Visual Components:
    ─────────────────
    1. Blue bars: Height represents absolute minimum price for each day
    2. Black step line: Shows how price changed throughout the day
    3. White text boxes: Display price information and time windows
    4. Gray X markers: Indicate days with no available data
    5. Grid lines: Horizontal guides for price reading

    Label Format Logic:
    ──────────────────
    Case 1: Stable minimum equals absolute minimum
        Display: "min: 1.539 €"
                "09:00-14:00"

    Case 2: Stable minimum higher than absolute minimum
        Display: "min: 1.535 €"
                "≥30m: 1.539 €"
                "14:00-18:00"

    Case 3: No stable minimum found (all prices too brief)
        Display: "min: 1.539 €"
                (no time windows shown)

    Interactive Features:
    ────────────────────
    - Zoom: Mouse wheel or toolbar buttons
    - Pan: Click and drag
    - Save: Toolbar save button (exports PNG/PDF/SVG)
    - Reset: Home button returns to original view

    Note:
        The plot is sized to accommodate up to 14 days comfortably.
        For longer periods, consider adjusting the figure width.
    """
    # ──────────────────────────────────────────────────────────────────────────
    # Create figure and axes
    # ──────────────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(15, 5), dpi=100)

    # ──────────────────────────────────────────────────────────────────────────
    # Setup x-axis positions
    # ──────────────────────────────────────────────────────────────────────────
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
        label='Tagestiefstpreis',
        zorder=2
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Mark days with missing data
    # ──────────────────────────────────────────────────────────────────────────
    missing_positions = [x for x, exists in zip(x_positions, has_data) if not exists]
    if missing_positions:
        ax.scatter(
            missing_positions,
            [1.55] * len(missing_positions),  # Middle of y-axis range
            marker='x',
            s=100,
            color='lightgray',
            alpha=0.5,
            label='Keine Daten',
            zorder=3
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Add labels and intraday progression for each day with data
    # ──────────────────────────────────────────────────────────────────────────
    for idx, row in df_complete.iterrows():
        if pd.isna(row['abs_min']):
            continue  # Skip days with no data

        day = row['date']
        x_pos = x_positions[idx]
        abs_price = float(row['abs_min'])
        stable_price = row['stable_min']
        intervals = daily_info.get(day, {}).get('stable_intervals', [])

        # ──────────────────────────────────────────────────────────────────────
        # Format time interval text
        # ──────────────────────────────────────────────────────────────────────
        interval_text = "\n".join(
            f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
            for start, end in intervals
        )

        # ──────────────────────────────────────────────────────────────────────
        # Build label text based on price relationship
        # ──────────────────────────────────────────────────────────────────────
        label_lines = [f"min: {abs_price:.3f} €"]

        if stable_price is not None and not pd.isna(stable_price):
            if float(stable_price) != abs_price:
                # Stable minimum is higher (absolute minimum was too brief)
                label_lines.append(
                    f"≥{STABLE_MIN_DURATION_MINUTES}m: {float(stable_price):.3f} €"
                )
                if interval_text:
                    label_lines.append(interval_text)
            else:
                # Stable minimum equals absolute minimum (good scenario!)
                if interval_text:
                    label_lines.append(interval_text)

        label = "\n".join(label_lines)

        # ──────────────────────────────────────────────────────────────────────
        # Place label inside bar with white background for readability
        # ──────────────────────────────────────────────────────────────────────
        ax.text(
            x_pos,
            abs_price - 0.1,
            label,
            ha='center',
            va='top',
            fontsize=10,
            bbox=dict(
                boxstyle='round,pad=0.3',
                facecolor='white',
                alpha=0.8,
                edgecolor='gray',
                linewidth=0.5
            ),
            zorder=5
        )

        # ──────────────────────────────────────────────────────────────────────
        # Draw intraday price progression (step plot)
        # ──────────────────────────────────────────────────────────────────────
        day_data = df[df['date'] == day].sort_values('timestamp')

        if len(day_data) >= 2:
            times = day_data['timestamp']
            raw_prices = day_data[FUEL_TYPE]

            # Normalize timestamps to fit within bar width
            minutes = times.dt.hour * 60 + times.dt.minute
            denom = (minutes.max() - minutes.min()) or 1
            normalized = (minutes - minutes.min()) / denom
            x_values = x_pos - 0.4 + normalized * 0.8  # Scale to bar width

            # Draw step plot (price constant until next change)
            ax.step(
                x_values,
                raw_prices,
                where='post',
                color='black',
                linewidth=1.5,
                zorder=4
            )

            # Add time labels at each price change point
            for x, y, t in zip(x_values, raw_prices, times.dt.strftime('%H:%M')):
                ax.text(
                    x,
                    y - 0.003,
                    t,
                    fontsize=7,
                    ha='center',
                    va='top',
                    rotation=45,
                    zorder=6
                )

    # ──────────────────────────────────────────────────────────────────────────
    # Format axes and appearance
    # ──────────────────────────────────────────────────────────────────────────
 
    ax.set_ylim(min_price, max_price)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(df_complete['date_str'], rotation=45, ha='right')
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

    # Add legend if there are missing days
    if missing_positions:
        ax.legend(loc='upper right', fontsize=10)

    # Adjust layout to prevent label cutoff
    plt.tight_layout()

    # Display interactive plot
    plt.show()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Main execution function - orchestrates the complete analysis pipeline.

    Pipeline Stages:
    ───────────────
    1. Data Loading: Read and preprocess CSV file
    2. Price Analysis: Calculate daily minimums and stable minimums
    3. Date Range: Create complete date range with gaps
    4. Visualization: Generate interactive plot

    This function serves as the entry point when the script is run directly
    from the command line or IDE.

    Console Output:
    ──────────────
    - Configuration summary
    - Data loading status
    - Record counts and date ranges
    - Progress messages
    - Error messages (if any issues occur)

    Example Console Output:
        Loading fuel price data from: ../data/log/diesel_prices_3.csv
        Analyzing last 7 days...
        Stable minimum threshold: 30 minutes

        Loaded 245 price observations
        Date range: 2026-01-02 to 2026-01-08

        Generating visualization...
        Done!
    """
    print("=" * 70)
    print("Fuel Price Visualization Tool - Processed Data")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Data file: {DATA_FILE}")
    print(f"  Analysis window: Last {SHOW_DAYS} days")
    print(f"  Stable minimum threshold: {STABLE_MIN_DURATION_MINUTES} minutes")
    print(f"  Business hours: {DAY_START.strftime('%H:%M')} - {DAY_END.strftime('%H:%M')}")
    print("\n" + "-" * 70)

    # ──────────────────────────────────────────────────────────────────────────
    # Load and preprocess data
    # ──────────────────────────────────────────────────────────────────────────
    print("\nLoading data...")
    df = load_and_prepare_data(DATA_FILE)

    if df.empty:
        print("\n[ERROR] No valid data found.")
        print("        Please check that the file exists and contains valid data.")
        return

    print(f"[OK] Loaded {len(df)} price observations")
    print(f"[OK] Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"[OK] Unique days: {df['date'].nunique()}")

    # ──────────────────────────────────────────────────────────────────────────
    # Analyze daily minimums
    # ──────────────────────────────────────────────────────────────────────────
    print("\nAnalyzing daily minimum prices...")
    daily_info = get_daily_min_info(
        df,
        stable_duration_minutes=STABLE_MIN_DURATION_MINUTES
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Create complete date range
    # ──────────────────────────────────────────────────────────────────────────
    print("Creating complete date range...")
    df_complete = create_complete_date_range(SHOW_DAYS, daily_info)

    # ──────────────────────────────────────────────────────────────────────────
    # Generate visualization
    # ──────────────────────────────────────────────────────────────────────────
    print("Generating visualization...")
    print("\n" + "=" * 70)
    plot_daily_lows(df, df_complete, daily_info)

    print("\n[OK] Done! Close the plot window to exit.")


if __name__ == '__main__':
    main()