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
SEPERATOR = ';'
show_days = 7

# "Stable minimum" definition
STABLE_MIN_DURATION_MINUTES = 30  # must last at least this long (segment-based)

# Data window (only show within this day-range)
DAY_START = time(9, 0)
DAY_END = time(22, 0)

# If timestamps occur outside [08:00, 22:01), shift them to next day 09:00
SHIFT_BEFORE = time(8, 0)
SHIFT_AFTER_EQ = time(22, 1)



# ──────────────────────────────────────────────────────────────────────────────
# 1. Load and preprocess data
# ──────────────────────────────────────────────────────────────────────────────
def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    """
    Load fuel price data from CSV and prepare it:
    - Parse timestamps
    - Shift prices outside 08:00–22:00 to next day 09:00
    - Keep only 09:00–22:00
    - Filter to recent days (show_days)
    - Add a synthetic 22:00 entry per day (clone last price) to "close" the day
    """
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"Datei '{filepath}' nicht gefunden.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, sep=SEPERATOR, engine='python')

    if 'date' not in df.columns:
        print("Keine 'date'-Spalte gefunden.")
        return pd.DataFrame()

    df['timestamp'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True).dt.tz_localize(None)
    df.dropna(subset=['timestamp'], inplace=True)


    # --- Step 1: late-night (>=22:01) -> keep only latest per day, move to next day 00:01 ---
    late_mask = df['timestamp'].dt.time >= SHIFT_AFTER_EQ
    if late_mask.any():
        late = df.loc[late_mask].copy()
        late['day'] = late['timestamp'].dt.date

        # keep only latest late-night per day
        idx_latest_late = late.groupby('day')['timestamp'].idxmax()
        kept_late = late.loc[idx_latest_late].copy()

        # shift to next day 00:01
        kept_late['timestamp'] = kept_late['timestamp'].dt.floor('D') + timedelta(days=1, minutes=1)

        # remove all original late-night rows, add shifted kept_late
        df = pd.concat(
            [df.loc[~late_mask].copy(), kept_late.drop(columns=['day'])],
            ignore_index=True
        )

# --- Step 2: early (<08:00) -> keep only latest per day, move to SAME day 09:00 ---
# IMPORTANT: this now also considers the 00:01 carry-over from step 1
    early_mask = df['timestamp'].dt.time < SHIFT_BEFORE
    if early_mask.any():
        early = df.loc[early_mask].copy()
        early['day'] = early['timestamp'].dt.date

        # keep only latest early per day
        idx_latest_early = early.groupby('day')['timestamp'].idxmax()
        kept_early = early.loc[idx_latest_early].copy()

        # shift to same day 09:00
        kept_early['timestamp'] = kept_early['timestamp'].dt.floor('D') + timedelta(hours=9)

        # remove all early rows, add shifted kept_early
        df = pd.concat(
            [df.loc[~early_mask].copy(), kept_early.drop(columns=['day'])],
            ignore_index=True
        )

    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)


    # Helper date column
    df['date'] = df['timestamp'].dt.date

    # Keep only 09:00–22:00 entries
    df = df[(df['timestamp'].dt.time >= DAY_START) & (df['timestamp'].dt.time <= DAY_END)]

    # Filter to configured number of days
    cutoff = date.today() - timedelta(days=show_days - 1)
    df = df[df['date'] >= cutoff]

    if df.empty:
        return df

    # Add synthetic 22:00 entries (to close the day visually + segment duration)
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


# ──────────────────────────────────────────────────────────────────────────────
# 2. Build price segments (each price lasts until next timestamp)
# ──────────────────────────────────────────────────────────────────────────────
def build_price_segments(day_group: pd.DataFrame):
    """
    Convert a day's observations into piecewise-constant segments:
      (start_ts, end_ts, price_at_start)
    Each segment lasts until the next timestamp.
    """
    g = day_group.sort_values('timestamp').reset_index(drop=True)
    segs = []
    if len(g) < 2:
        return segs

    for i in range(len(g) - 1):
        start = g.loc[i, 'timestamp']
        end = g.loc[i + 1, 'timestamp']
        price = float(g.loc[i, 'diesel'])

        if end > start:
            segs.append((start, end, price))

    return segs


# ──────────────────────────────────────────────────────────────────────────────
# 3. Compute per-day min + stable-min (segment-based)
# ──────────────────────────────────────────────────────────────────────────────
def get_daily_min_info(df: pd.DataFrame, stable_duration_minutes: int = STABLE_MIN_DURATION_MINUTES) -> dict:
    """
    For each day:
      - abs_min: absolute minimum of observed prices that day
      - stable_min: cheapest price that persists for >= stable_duration_minutes
      - stable_intervals: time windows for stable_min (merged over consecutive segments)

    "Persists" means from one timestamp to the next (segment-based).
    """
    out = {}

    for day, group in df.groupby('date'):
        group = group.sort_values('timestamp')

        abs_min = float(group['diesel'].min()) if not group.empty else None

        segments = build_price_segments(group)

        # Merge consecutive segments with same price into intervals
        intervals_by_price = {}  # price -> [(start,end), ...]
        if segments:
            cur_start, cur_end, cur_price = segments[0]

            for start, end, price in segments[1:]:
                if price == cur_price and start == cur_end:
                    cur_end = end
                else:
                    intervals_by_price.setdefault(cur_price, []).append((cur_start, cur_end))
                    cur_start, cur_end, cur_price = start, end, price

            intervals_by_price.setdefault(cur_price, []).append((cur_start, cur_end))

        # Find stable minimum
        stable_min = None
        stable_intervals = []
        for price in sorted(intervals_by_price.keys()):
            qualifying = [
                (s, e) for (s, e) in intervals_by_price[price]
                if (e - s).total_seconds() / 60 >= stable_duration_minutes
            ]
            if qualifying:
                stable_min = float(price)
                stable_intervals = qualifying
                break

        out[day] = {
            'abs_min': abs_min,
            'stable_min': stable_min,
            'stable_intervals': stable_intervals,
        }

    return out


# ──────────────────────────────────────────────────────────────────────────────
# 4. Complete date range for gaps
# ──────────────────────────────────────────────────────────────────────────────
def create_complete_date_range(num_days: int, daily_info: dict) -> pd.DataFrame:
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days - 1)

    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    df_complete = pd.DataFrame({
        'date': all_dates.date,
        'date_str': all_dates.strftime('%d.%m.%Y')
    })

    df_complete['abs_min'] = df_complete['date'].map(lambda d: daily_info.get(d, {}).get('abs_min'))
    df_complete['stable_min'] = df_complete['date'].map(lambda d: daily_info.get(d, {}).get('stable_min'))

    return df_complete


# ──────────────────────────────────────────────────────────────────────────────
# 5. Plot
# ──────────────────────────────────────────────────────────────────────────────
def plot_daily_lows(df: pd.DataFrame, df_complete: pd.DataFrame, daily_info: dict):
    fig, ax = plt.subplots(figsize=(15, 5), dpi=100)

    x_positions = list(range(len(df_complete)))
    has_data = df_complete['abs_min'].notna()

    # Bars: absolute min per day
    bars = ax.bar(
        [x for x, exists in zip(x_positions, has_data) if exists],
        df_complete.loc[has_data, 'abs_min'],
        color='C0',
        width=0.8
    )

    # Missing days
    missing_positions = [x for x, exists in zip(x_positions, has_data) if not exists]
    if missing_positions:
        ax.scatter(
            missing_positions,
            [1.55] * len(missing_positions),
            marker='x',
            s=100,
            color='lightgray',
            alpha=0.5,
            label='Keine Daten'
        )

    # Labels + intraday step plot
    bar_idx = 0
    for idx, row in df_complete.iterrows():
        if pd.isna(row['abs_min']):
            continue

        day = row['date']
        x_pos = x_positions[idx]
        abs_price = float(row['abs_min'])
        stable_price = row['stable_min']
        intervals = daily_info.get(day, {}).get('stable_intervals', [])

        interval_text = "\n".join(
            f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in intervals
        )

        # Label logic:
        # - always show abs min
        # - if stable_min differs: show "≥30m: ..."
        # - if stable_min equals abs_min: don't show "≥30m", show timeframe only
        label_lines = [f"min: {abs_price:.3f} €"]

        if stable_price is not None and not pd.isna(stable_price):
            if float(stable_price) != abs_price:
                label_lines.append(f"≥{STABLE_MIN_DURATION_MINUTES}m: {float(stable_price):.3f} €")
                if interval_text:
                    label_lines.append(interval_text)
            else:
                if interval_text:
                    label_lines.append(interval_text)

        label = "\n".join(label_lines)

        # Move label block lower inside the bar
        ax.text(
            x_pos,
            abs_price - 0.1,
            label,
            ha='center',
            va='top',
            fontsize=10
        )

        # Intraday step plot (from one timestamp to the next visually)
        day_data = df[df['date'] == day].sort_values('timestamp')
        if len(day_data) >= 2:
            times = day_data['timestamp']
            raw_prices = day_data['diesel']

            minutes = times.dt.hour * 60 + times.dt.minute
            denom = (minutes.max() - minutes.min()) or 1
            normalized = (minutes - minutes.min()) / denom
            x_values = x_pos - 0.4 + normalized * 0.8

            ax.step(x_values, raw_prices, where='post', color='black', linewidth=1.5)

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
# 6. Main
# ──────────────────────────────────────────────────────────────────────────────
def show_daily_lows():
    df = load_and_prepare_data(DATA_FILE)
    if df.empty:
        print("Keine gültigen Daten in der Datei.")
        return

    daily_info = get_daily_min_info(df, stable_duration_minutes=STABLE_MIN_DURATION_MINUTES)
    df_complete = create_complete_date_range(show_days, daily_info)

    plot_daily_lows(df, df_complete, daily_info)


if __name__ == '__main__':
    show_daily_lows()
