@echo off
REM Berechne das heutige Datum und ziehe einen Tag ab, um den Vortag zu erhalten
for /F "tokens=1-4 delims=-" %%a in ("%date%") do (
    set year=%%a
    set month=%%b
    set day=%%c
)

REM Verringere den Tag um 1 für den Vortag
set /a day=%day%-1

REM Wenn der Tag 0 wird (z.B. für den 1. des Monats), muss der Monat und das Jahr angepasst werden
if %day% lss 1 (
    set /a month=%month%-1
    if %month% lss 1 (
        set month=12
        set /a year=%year%-1
    )
    set day=31
)

REM Erstelle den Dateipfad und Dateinamen im Format stations/YYYY/MM/YYYY-MM-DD-stations.csv
set filepath=stations\%year%\%month%\%year%-%month%-%day%-stations.csv

REM Gehe ins Verzeichnis des Repositories
cd C:\path\to\tankerkoenig-data

REM Hole die neuesten Änderungen aus dem Repository
git pull origin main

REM Lade die Datei herunter, die dem Vortag entspricht
git checkout origin/main -- %filepath%

REM Beende das Skript
exit
