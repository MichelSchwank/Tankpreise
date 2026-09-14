import pandas as pd
import datetime

# Path to the dataset (CSV file)
DATA_FILE = '2025_06.csv'  # Adjust path as necessary

def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    # Load CSV file into DataFrame
    df = pd.read_csv(filepath, sep=',', engine='python')
    
    # Ensure that 'date' column is properly converted to datetime
    df['timestamp'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True)
    df.dropna(subset=['timestamp'], inplace=True)
    
    # Extract the date part from the timestamp
    df['date'] = df['timestamp'].dt.date

    return df

def add_2200_entry_per_day(df: pd.DataFrame) -> pd.DataFrame:
    # Create an empty DataFrame to store the new rows
    additional_rows = []

    # Group the data by date
    for date, group in df.groupby('date'):
        # Get the latest entry for each day
        latest_entry = group.iloc[-1]
        
        # Set the timestamp for 22:00 of the current day
        new_timestamp = datetime.datetime.combine(date, datetime.time(22, 0))
        
        # Create a new entry with the same values but updated timestamp
        new_entry = latest_entry.copy()
        new_entry['timestamp'] = new_timestamp
        new_entry['date'] = date
        
        # Append the new row to the list of additional rows
        additional_rows.append(new_entry)

    # Convert the list of new rows to a DataFrame
    additional_df = pd.DataFrame(additional_rows)

    # Combine the original DataFrame with the new 22:00 entries
    return pd.concat([df, additional_df], ignore_index=True)

def save_to_csv(df: pd.DataFrame, output_filepath: str):
    # Save the updated DataFrame to a new CSV file
    df.to_csv(output_filepath, index=False)

def main():
    # Load and prepare the data
    df = load_and_prepare_data(DATA_FILE)
    
    # Add the 22:00 entries
    df_updated = add_2200_entry_per_day(df)
    
    # Save the updated dataset to a new file
    save_to_csv(df_updated, 'updated_2025_06.csv')

    print("Data processing completed. The updated file is 'updated_2025_06.csv'.")

if __name__ == '__main__':
    main()
