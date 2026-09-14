# Tankpreise - Fuel Price Tracking & Visualization

A personal diesel/E5/E10 price tracking project for a handful of gas stations
near Ludgeri/Steinfurt/Wentorf. Price history comes from a local clone of the
public [tankerkoenig-data](https://github.com/tankerkoenig/tankerkoenig-data)
repository (community-donated dumps of the Tankerkönig API); the scripts in
`src2/` pull the relevant rows out of that dataset and chart daily/intraday
price patterns to spot good refueling windows.

## Project Structure

```
Tankpreise/
├── src2/                        # Active source code
│   ├── extract.py                        # Pull one station's rows out of the cloned dataset
│   ├── visualize_myData.py               # Single-fuel chart, ~14 days, intraday detail
│   ├── visualize_myData_longterm.py      # Same, but a long window (148 days), thinned labels
│   └── visualise_tankerData_fuel_type.py # Chart a single dated raw extract, fuel type via CLI arg
│
├── data/
│   ├── raw/                   # Per-station extracts from extract.py (gitignored, .gitkeep only)
│   ├── processed/             # Consolidated per-fuel CSVs consumed by visualize_myData*.py (gitignored)
│   └── archive/               # Old/test data files (gitignored)
│
├── scripts/                    # Windows batch helpers
│   ├── repo_clone.bat         # git pull the tankerkoenig-data repo (hardcoded local path)
│   └── file_clone.bat         # Check out a single day's file from tankerkoenig-data
│
├── output/                     # Generated charts (gitignored)
│
├── legacy/                     # Superseded development iterations, kept for reference
│   ├── src/, visualizations/  # Earlier versions of the extract/visualize scripts
│   └── utilities/             # Includes two standalone live-polling scripts that call the
│                               # Tankerkönig API directly (see "Live polling" below)
│
├── docs/
│   └── projectstructure.md    # Older structure writeup — describes a previous src/ layout,
│                               # now stale; see this README instead
│
└── pyproject.toml              # Project metadata & dependencies (pandas, matplotlib)
```

## Setup

- Python ≥ 3.10 (`.venv/` in this repo, dependencies declared in `pyproject.toml`).
- Clone `tankerkoenig-data` as a **sibling** of this repo (the scripts reference it via
  `../../tankerkoenig-data`), then keep it updated with `scripts/repo_clone.bat`
  (edit the hardcoded path inside first) or a plain `git pull`.
- `TANKERKOENIG_API_KEY` is **only** needed for the legacy live-polling scripts
  (see below) — the current `src2/` pipeline reads from the cloned dataset and
  doesn't call the live API, so it needs no key.

## Workflow

### 1. Update the data source
```bash
cd ../tankerkoenig-data
git pull
```
or run `scripts/repo_clone.bat`.

### 2. Extract station data
```bash
cd src2
python extract.py
```
Edit `STATION_NAME` (and `MONTHS_TO_PROCESS`) at the top of the file to pick the
station and lookback window. Outputs a comma-separated CSV to `data/raw/`.

### 3. Consolidate into `data/processed/` (manual step, no script yet)
`visualize_myData.py` / `visualize_myData_longterm.py` expect semicolon-separated
files at `data/processed/{diesel,e5,e10}_prices_*.csv` with columns
`date;<fuel>;station`. There's currently no committed script that builds these
from the `data/raw/` extracts — they've been assembled by hand so far. This is
the main gap in the pipeline (see Known Gaps below).

### 4. Visualize
```bash
cd src2
python visualize_myData.py              # last SHOW_DAYS (default 14), one fuel/station, intraday detail
python visualize_myData_longterm.py     # long window (default 148 days), thinned x-axis
python visualise_tankerData_fuel_type.py [diesel|e5|e10]   # one dated data/raw/ file, single day snapshot
```
Fuel type, station, and date range are set as constants near the top of each
file (`FUEL_TYPE`, `STATION`, `SHOW_DAYS`, `Gasstation`, `Datum`, ...).

## Features

- **Smart time handling**: shifts late-night entries (≥21:40) to 00:01 next day
  and early-morning entries (<08:00/09:00) to 09:00, so overnight carryover
  prices don't distort the business-hours view.
- **Stable-minimum detection**: alongside the absolute daily low, finds the
  cheapest price that held for ≥30 minutes — more actionable than a price that
  flashed by for a minute.
- **Multi-station support**: `data/processed/` CSVs carry a `station` column so
  several stations' history can live in the same file.
- **Missing-day indicators**: days with no data are marked with gray ✕ markers
  instead of silently disappearing from the x-axis.

## Live polling (legacy, needs `TANKERKOENIG_API_KEY`)

`legacy/utilities/gas_price.py` and `gas_price_datetime.py` poll the live
Tankerkönig API directly (`creativecommons.tankerkoenig.de/json/prices.php`)
and append the current price to a CSV — this is where `TANKERKOENIG_API_KEY`
is actually read (`os.environ.get('TANKERKOENIG_API_KEY')`). These aren't part
of the current `src2/` pipeline; they'd need to be run on a schedule (e.g. a
Task Scheduler job) to build up history independently of the
`tankerkoenig-data` repo.

## Known Gaps / TODO

- No script to turn `data/raw/` extracts into the `data/processed/` files the
  visualizers expect — currently a manual step.
- The `STATIONS` UUID dict is duplicated between `extract.py` and
  `visualise_tankerData_fuel_type.py`; worth factoring out.
- `visualise_tankerData_fuel_type.py`'s `STATIONS["Orlen_Wentorf"]` UUID has
  stray characters (`0050´ßoicxäiuzt56ba-...`) — looks like an accidental edit,
  not a real UUID.
- `docs/projectstructure.md` describes an older `src/` layout and is stale;
  either update it to match `src2/` or remove it in favor of this README.

## Dependencies

- pandas
- matplotlib

(see `pyproject.toml` for pinned minimum versions)
