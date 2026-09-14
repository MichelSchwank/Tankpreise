"""
Extract gas station price data from tankerkoenig CSV files.

This script processes CSV files from the tankerkoenig-data repository and extracts
price information for specific gas stations based on their UUIDs.
"""

import os
from pathlib import Path
from typing import List, Tuple
from datetime import datetime, timedelta
import pandas as pd


    # Configuration
STATION_NAME = "Tanke_Lud"  # Change this to extract different stations
MONTHS_TO_PROCESS = 1  # Look back up to 2 months
# be patient, this can take 30s-100s

# Gas Station UUIDs
STATIONS = {
    "Tanke_Lud": "916d61b6-7279-4d63-a754-ae160f8cdee2",
    "Tanke_Steinf": "291fafe3-dbfb-4452-8c68-aa6a7540ce98",
    "Wentorf_Hem": "e1a15081-2543-9107-e040-0b0a3dfe563c",
    "MrWash": "21d8e11f-5712-4d00-81aa-100887b65699",
    "EDEKA_Wentorf": "2f432c0c-9052-466d-9030-c78ab8c4149d",
    "München": "fb79c457-543a-4ff6-ba70-cd270ac2110a",
    "Orlen_Wentorf": "005056ba-7cb6-1ed2-bceb-bbb7e74e0d4e",
}


class TankDataExtractor:
    """Extracts price data for specific gas stations from CSV files."""

    def __init__(self, station_uuid: str, station_name: str):
        """
        Initialize the data extractor.

        Args:
            station_uuid: The UUID of the gas station to extract data for
            station_name: The name of the station for output file naming
        """
        self.station_uuid = station_uuid
        self.station_name = station_name
        self.script_dir = Path(__file__).parent
        self.base_data_dir = self.script_dir / '../../tankerkoenig-data/prices'

    def get_date_range(self, months_back: int = 1) -> List[Tuple[str, Path]]:
        """
        Get the date range and corresponding directories to search.

        Args:
            months_back: Number of months to look back (default: 1 for current month only)

        Returns:
            List of tuples containing (date_prefix, directory_path)
        """
        date_ranges = []
        current_date = datetime.now()

        for i in range(months_back):
            target_date = current_date - timedelta(days=30 * i)
            year = target_date.year
            month = f"{target_date.month:02d}"
            date_prefix = f"{year}-{month}"
            directory = self.base_data_dir / str(year) / month

            if directory.exists():
                date_ranges.append((date_prefix, directory))

        return date_ranges

    def extract_from_file(self, file_path: Path) -> List[Tuple]:
        """
        Extract matching rows from a single CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            List of matching rows
        """
        matching_rows = []

        try:
            df = pd.read_csv(file_path, delimiter=',')

            # Extract rows that contain the station UUID
            for row in df.itertuples(index=False):
                if any(isinstance(cell, str) and self.station_uuid in cell for cell in row):
                    matching_rows.append(row)

        except Exception as e:
            print(f"Error reading file {file_path.name}: {e}")

        return matching_rows

    def extract_data(self, months_back: int = 1) -> pd.DataFrame:
        """
        Extract data from all relevant CSV files.

        Args:
            months_back: Number of months to look back

        Returns:
            DataFrame containing all extracted data
        """
        all_extracted_data = []
        date_ranges = self.get_date_range(months_back)

        if not date_ranges:
            print("No valid data directories found.")
            return pd.DataFrame()

        for date_prefix, directory in date_ranges:
            print(f"Processing files from {directory}...")

            if not directory.exists():
                print(f"Directory does not exist: {directory}")
                continue

            # Process all CSV files matching the date prefix
            for filename in os.listdir(directory):
                if filename.endswith('.csv') and filename.startswith(date_prefix):
                    file_path = directory / filename
                    extracted_rows = self.extract_from_file(file_path)
                    all_extracted_data.extend(extracted_rows)

        if all_extracted_data:
            return pd.DataFrame(all_extracted_data)
        else:
            return pd.DataFrame()

    def save_data(self, df: pd.DataFrame, output_path: Path = None) -> None:
        """
        Save extracted data to CSV file.

        Args:
            df: DataFrame to save
            output_path: Custom output path (optional)
        """
        if df.empty:
            print("No matching data found.")
            return

        if output_path is None:
            today = datetime.now().strftime("%Y_%m_%d")
            output_path = self.script_dir / f'../data/raw/{today}_{self.station_name}.csv'

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_path, index=False)
        print(f"Data successfully extracted and saved to {output_path}")
        print(f"Total rows extracted: {len(df)}")


def main():
    """Main execution function."""


    # Initialize extractor
    station_uuid = STATIONS.get(STATION_NAME)
    if not station_uuid:
        print(f"Error: Station '{STATION_NAME}' not found in STATIONS dictionary.")
        return

    extractor = TankDataExtractor(station_uuid, STATION_NAME)

    # Extract and save data
    print(f"Extracting data for {STATION_NAME} ({station_uuid})")
    df = extractor.extract_data(months_back=MONTHS_TO_PROCESS)
    extractor.save_data(df)


if __name__ == "__main__":
    main()


###
# Notes:
# 1. Update the tankerkoenig-data repo before running this script
# 2. Run this extraction, then proceed to visualization
#
# Completed improvements:
# - Automatically determines current month (no manual updates needed)
# - Supports looking back multiple months via MONTHS_TO_PROCESS parameter
# - Better code organization with class-based structure
# - Automatic output file naming with current date
# - Improved error handling and user feedback
#
# TODO:
# - Change night values to 6am (handle in transformation step)
