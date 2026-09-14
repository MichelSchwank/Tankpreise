# Tankpreise - Fuel Price Tracking & Visualization

A personal diesel/E5/E10 price tracking project for a handful of gas stations
near Ludgeri/Steinfurt/Wentorf. Two independent sources feed it:

1. **Live polling** — `src2/record_prices.py` calls the live Tankerkönig API
   every few minutes (via an external scheduler) and appends to `data/log/`.
   This is the primary, continuously growing dataset.
2. **Historical import** — `src2/extract.py` pulls rows out of a local clone
   of the public [tankerkoenig-data](https://github.com/tankerkoenig/tankerkoenig-data)
   repo (community-donated dumps) into `data/import/`, for stretches of
   history that predate or gap the live polling.

The `src2/visualize_*.py` scripts chart daily/intraday price patterns from
whichever of the two you point them at, to spot good refueling windows.

## Project Structure

```
Tankpreise/
├── src2/                        # All active source code
│   ├── stations.py                       # Shared station-name -> Tankerkönig UUID registry
│   ├── extract.py                        # Historical import: pull one station's rows out of the cloned dataset
│   ├── record_prices.py                  # ACTIVE: scheduled live poller, writes data/log/
│   ├── visualize_myData.py               # Single-fuel chart, ~14 days, intraday detail (reads data/log/)
│   ├── visualize_myData_longterm.py      # Same, but a long window (148 days), thinned labels
│   └── visualise_tankerData_fuel_type.py # Chart a single dated data/import/ extract, fuel type via CLI arg
│
├── data/
│   ├── import/                # Per-station historical extracts from extract.py (gitignored, .gitkeep only)
│   ├── log/                   # Live per-fuel price log from record_prices.py (gitignored)
│   └── archive/               # Old/test data files (gitignored)
│
├── scripts/                    # Windows batch helpers
│   ├── repo_clone.bat         # git pull the tankerkoenig-data repo (hardcoded local path)
│   └── file_clone.bat         # Check out a single day's file from tankerkoenig-data
│
├── output/                     # Generated charts (gitignored)
│
└── pyproject.toml              # Project metadata & dependencies (pandas, matplotlib)
```

There used to be a `legacy/` folder full of superseded development iterations
and a stale `docs/projectstructure.md`; both have been removed now that this
README is accurate and `record_prices.py` (formerly buried in
`legacy/utilities/gas_price_datetime.py`) has been promoted into `src2/`
alongside the rest of the active code.

## Setup

- Python ≥ 3.10 (`.venv/` in this repo, dependencies declared in `pyproject.toml`).
- `TANKERKOENIG_API_KEY` **is required** — `record_prices.py` reads it via
  `os.environ.get('TANKERKOENIG_API_KEY')` on every scheduled run. Set it as a
  persistent user environment variable (e.g. `setx TANKERKOENIG_API_KEY "..."`
  on Windows) so it survives outside whichever terminal set it, since the
  poller runs unattended on a schedule.
- For the historical import path only: clone `tankerkoenig-data` as a
  **sibling** of this repo (`extract.py` references it via
  `../../tankerkoenig-data`), then keep it updated with `scripts/repo_clone.bat`
  (edit the hardcoded path inside first) or a plain `git pull`.
- ⚠️ If you're reading this after the `legacy/utilities/gas_price_datetime.py`
  → `src2/record_prices.py` move: update the scheduled task's command line to
  point at the new path, or the live log will silently stop growing.

## Workflow

### Live price log (`data/log/`)
`record_prices.py` is run on a recurring schedule (external to this repo —
e.g. Windows Task Scheduler) roughly every few minutes. Each run:
- fetches all stations in `stations.STATIONS` in one API call,
- appends one row per open station/fuel to `data/log/{diesel,e5,e10}_prices_*.csv`
  (semicolon-separated, columns `date;station;<fuel>`).

No manual step needed as long as the scheduled job keeps running and the API
key stays set.

### Historical import (`data/import/`)
```bash
cd ../tankerkoenig-data && git pull        # or scripts/repo_clone.bat
cd src2
python extract.py
```
Edit `STATION_NAME` (and `MONTHS_TO_PROCESS`) at the top of `extract.py` to
pick the station and lookback window. Outputs a comma-separated,
Tankerkönig-shaped CSV to `data/import/<date>_<station>.csv` — used to fill in
history the live poller didn't capture, or via
`visualise_tankerData_fuel_type.py` for a one-off look at a single day.

### Visualize
```bash
cd src2
python visualize_myData.py              # last SHOW_DAYS (default 14), one fuel/station, intraday detail
python visualize_myData_longterm.py     # long window (default 148 days), thinned x-axis
python visualise_tankerData_fuel_type.py [diesel|e5|e10]   # one dated data/import/ file, single day snapshot
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
- **Multi-station support**: `data/log/` CSVs carry a `station` column so
  several stations' history can live in the same file.
- **Missing-day indicators**: days with no data are marked with gray ✕ markers
  instead of silently disappearing from the x-axis.

## Known Gaps / TODO

- The scheduled task that runs `record_prices.py` isn't tracked anywhere in
  this repo (no exported Task Scheduler XML, no documented interval) — if the
  machine is rebuilt, that scheduling has to be recreated from memory.
- `scripts/repo_clone.bat` and `scripts/file_clone.bat` still hardcode
  machine-specific absolute paths to the `tankerkoenig-data` clone — edit
  those before running on another machine.

## Dependencies

- pandas
- matplotlib
- requests (used by `record_prices.py` to call the live Tankerkönig API)

(see `pyproject.toml` for pinned minimum versions)
