@echo off
echo Starting Caltrain Tracker...

REM Try using python command first
python caltrainTracker.py
if errorlevel 1 (
    REM If python command fails, try using the full path
    "C:\Users\Erik\AppData\Local\Programs\Python\Python313\python.exe" caltrainTracker.py
)

pause 