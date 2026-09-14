Project Structure Analysis: Fuel Price Tracking & Visualization
This is a diesel/gas price tracking and visualization project that pulls data from the Tankerkönig API and creates visual analysis of price trends. Here's the breakdown:

Main Workflow Files (numbered sequence)
1. 1_extract.py - Data Extraction
Purpose: Extracts specific gas station data from the Tankerkönig dataset What it does:
Searches through daily CSV files in tankerkoenig-data/prices/2025/06/
Filters rows containing specific gas station IDs (e.g., Ludgeri, Steinfurter, Wentorf)
Outputs a consolidated CSV file with data for one specific station
Key variables:
Tanke_Lud, Tanke_Steinf, Wentorf_Hem - Gas station UUIDs to filter
Output: 2_2025_06_28_Lud.csv (or similar)
Notes in code: Suggests updating repo first, then running extraction, then visualization
2. 2_clean_gas_visualisation_no_intervalls_step_starts_at_9_ends_at_22_cleancode.py - Clean Visualization (Current Version)
Purpose: Main visualization script with cleaned code and smart time handling What it does:
Loads diesel price data from CSV (semicolon-separated)
Shifts nighttime prices (before 08:00 or after 22:01) to next day at 09:00
Filters to only show 09:00-22:00 window
Shows last 90 days of data (show_days = 90)
Creates synthetic 22:00 entries to close each day's price curve
Generates bar chart with daily minimum prices
Overlays step plots showing intraday price changes
Groups consecutive timestamps with same price into intervals (max 800 min gap)
Configuration:
DATA_FILE = 'diesel_prices_3.csv'
MAX_GAP_MINUTES = 800 (13+ hours)
show_days = 90
SEPERATOR = ';'
Output: Interactive matplotlib chart showing daily lows with time labels
3. 4_gas_visualisation_times_intervalls_second_graph_high_and_times_excel_based.py - Legacy Excel-based Visualization
Purpose: Older version that works with comma-separated CSVs from Excel exports Differences from version 2:
Shorter time window (14 days instead of 90)
Comma-separated CSV instead of semicolon
Shows interval text directly on bars (17:30-19:45 format)
Subtracts 0 hours from timestamp (configurable line 29)
MAX_GAP_MINUTES = 280 (4.6 hours, stricter than v2)
Works with files like 2025_06_24_Westfalen.csv
Data Files
Input Data Sources:
tankerkoenig-data/ - Git repository with raw price data from Tankerkönig API
Daily CSV files organized by year/month (e.g., 2025/06/)
Processed CSV Files:
diesel_prices_3.csv - Main dataset (38KB, semicolon-separated)
Format: date;diesel
Example: 2025-06-20 11:07:00;1.559
Station-specific exports (from step 1):
2025_06_24_Westfalen.csv (94KB)
2025_06_27_steinfurter.csv (86KB)
2025_06_27_{Wentorf_Hem}.csv (82KB)
2025_06_25_westf.csv, 2025_06_28_Lud.csv, etc.
Legacy/test files:
2_2025_06.csv, aasee_2025_06.csv, aral_2025_06.csv, wash_2025_06.csv, etc.
Obsolete/Legacy Files (empty or superseded)
These files appear to be development iterations that are no longer used:
Empty files (0 bytes):
2_clean_gas_visualisation_no_intervalls.py
2_clean_gas_visualisation_no_intervalls_sep_sim.py
2_clean_gas_visualisation_no_intervalls_step.py
2_clean_gas_visualisation_no_intervalls_step_starts_at_9.py
new_sett_22_h.py
Older visualization scripts:
gas_visualisation_time.py (1.8KB)
gas_visualisation_times_intervalls.py (2.6KB)
gas_visualisation_times_intervalls_second_graph.py (3.3KB)
gas_visualisation_times_intervalls_second_graph_clean.py (3.8KB)
gas_visualisation_times_intervalls_second_graph_high_and_times.py (4.3KB)
gas_visualisation_times_intervalls_second_graph_high_and_times_alldata.py (4.8KB)
Other utility scripts:
gas_visualise.py (1.1KB) - Basic visualization
gas_price.py, gas_price_datetime.py - Simple price scripts
22_irnored.py - Appears to be a test file
Utility Files
file_clone.bat - Windows batch script (974 bytes)
repo_clone.bat - Git repository cloning script (264 bytes)
pyproject.toml - Python project metadata (Poetry/pip configuration)
Current Recommended Workflow
Based on file names and code comments:
Update data source:

cd tankerkoenig-data
git pull
Extract station data:

python 1_extract.py
Edit station UUID and output filename as needed
Outputs: 2_2025_06_28_Lud.csv (or similar)
Visualize prices:

python 2_clean_gas_visualisation_no_intervalls_step_starts_at_9_ends_at_22_cleancode.py
Uses diesel_prices_3.csv (semicolon-separated)
Shows 90 days, 09:00-22:00 window
Displays daily minimums with intraday price curves
Key Insights
Naming Convention Evolution:
Your file naming shows an iterative development process:
Started with basic visualization (gas_visualise.py)
Added time intervals → gas_visualisation_times_intervalls.py
Added second graph → ..._second_graph.py
Added high/low tracking → ..._high_and_times.py
Created "clean" versions → 2_clean_...
Added time window restrictions → ..._starts_at_9_ends_at_22.py
Final cleaned code → ..._cleancode.py
Best Practice Recommendation:
Consider using version control (git) instead of filename versioning. This would clean up your directory significantly. You could:
Initialize a git repo in this directory
Keep only the active files (1, 2, 4)
Delete empty/obsolete scripts
Commit working versions with meaningful messages
Would you like me to help you clean up this project structure or explain any specific file in more detail