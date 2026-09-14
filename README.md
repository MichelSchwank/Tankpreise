# Tankpreise - Fuel Price Tracking & Visualization

A diesel/gas price tracking and visualization project that pulls data from the Tankerkönig API and creates visual analysis of price trends.

## Project Structure

```
Tankpreise/
├── src/                        # Active source code
│   ├── 1_extract.py           # Extract gas station data from Tankerkönig dataset
│   └── 2_visualize.py         # Visualize price trends (90-day view, 09:00-22:00)
│
├── data/
│   ├── raw/                   # Raw extracted station data
│   ├── processed/             # Cleaned/processed datasets
│   └── archive/               # Old/test data files
│
├── scripts/                    # Utility batch scripts
│   ├── repo_clone.bat         # Clone Tankerkönig repository
│   └── file_clone.bat         # File operations
│
├── output/                     # Generated charts and reports
│
├── legacy/                     # Historical development files
│   ├── visualizations/        # Previous visualization iterations
│   └── utilities/             # Old utility scripts
│
└── docs/                       # Documentation
    └── projectstructure.md    # Detailed project analysis

```

## Quick Start

### 1. Update Data Source
```bash
cd tankerkoenig-data
git pull
```

### 2. Extract Station Data
```bash
cd src
python 1_extract.py
```
Edit station UUID and output filename as needed. Outputs to `data/raw/`.

### 3. Visualize Prices
```bash
cd src
python 2_visualize.py
```
Uses `data/processed/diesel_prices_3.csv` (semicolon-separated).
Shows as many days as desired, 09:00-22:00 window with daily minimums and intraday price curves.

## Configuration

### Station IDs (in 1_extract.py)
- `Tanke_Lud`: 916d61b6-7279-4d63-a754-ae160f8cdee2
- `Tanke_Steinf`: 291fafe3-dbfb-4452-8c68-aa6a7540ce98
- `Wentorf_Hem`: e1a15081-2543-9107-e040-0b0a3dfe563c

### Visualization Settings (in 2_visualize.py)
- `DATA_FILE`: Path to processed CSV file
- `MAX_GAP_MINUTES`: 800 (max gap between identical prices)
- `show_days`: 90 (number of days to display)
- `SEPERATOR`: ';' (CSV delimiter)

## Features

- **Smart Time Handling**: Shifts nighttime prices (before 08:00 or after 22:01) to next day at 09:00
- **Daily Minimums**: Bar chart showing lowest price each day
- **Intraday Trends**: Step plots overlay showing price changes throughout the day
- **Interval Grouping**: Groups consecutive timestamps with same price
- **Time Window**: Focuses on 09:00-22:00 shopping hours

## Data Sources

- **Tankerkönig API**: Raw price data from `tankerkoenig-data/prices/YYYY/MM/` directory
- **Processed Files**: Semicolon-separated CSV with format: `date;diesel`
  - Example: `2025-06-20 11:07:00;1.559`

## Dependencies

- pandas
- matplotlib

## Notes

- The project uses relative paths from the `src/` directory
- Legacy files contain development iterations and are kept for reference
- All output should go to the `output/` directory
