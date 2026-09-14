import os
import pandas as pd

Tanke_Lud = "916d61b6-7279-4d63-a754-ae160f8cdee2"
Tanke_Steinf = "291fafe3-dbfb-4452-8c68-aa6a7540ce98"
Wentorf_Hem = "e1a15081-2543-9107-e040-0b0a3dfe563c"

# Verzeichnis, in dem die Dateien liegen
directory = r'C:\Users\miche\OneDrive\Dokumente\3. Privat\VSC_Projects\tankerkoenig-data\prices\2025\06'  # Ersetze dies durch den Pfad zu deinem Ordner
output_csv = '2_2025_06_28_Lud.csv'  # Ausgabedatei

# Liste zum Speichern der extrahierten Daten
extracted_data = []

# Durchsuche alle Dateien im Verzeichnis
for filename in os.listdir(directory):
    if filename.endswith('.csv') and filename.startswith('2025-06'):
        file_path = os.path.join(directory, filename)
        
        # Versuche die Datei zu lesen
        try:
            # Wenn die Dateien CSV oder tabulatorgetrennt sind, verwende pandas
            df = pd.read_csv(file_path, delimiter=',')  # Falls Tabulatoren oder ein anderes Trennzeichen verwendet wird, ändere `delimiter`
            
            # Iteriere über alle Zellen und extrahiere nur die, die den gesuchten String enthalten
            for row in df.itertuples(index=False):
                for cell in row:
                    if isinstance(cell, str) and Tanke_Lud in cell:
                        extracted_data.append(row)
                        break  # Es reicht, nur eine Zelle mit dem String zu finden, um diese Zeile zu speichern
        except Exception as e:
            print(f"Fehler beim Lesen der Datei {filename}: {e}")
            continue

# Falls Daten extrahiert wurden, speichere sie in einer CSV-Datei
if extracted_data:
    extracted_df = pd.DataFrame(extracted_data)
    extracted_df.to_csv(output_csv, index=False)
    print(f'Daten erfolgreich extrahiert und in {output_csv} gespeichert.')
else:
    print('Keine passenden Daten gefunden.')



###
# notes
# update repo, then run this code then visualise 

# to do:
# change night values to 6am
# adapt repo call to get current month 
# adapt this code so that it looks at up to two months. think of first 13 days of a month