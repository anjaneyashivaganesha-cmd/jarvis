@echo off
title JARVIS
echo Starting JARVIS...
echo.

:: Start native service (always listening, even on lock screen)
cd /d C:\Users\suche\Documents\jarvis\backend
start "JARVIS Service" /MIN ".venv\Scripts\python.exe" jarvis_service.py

:: Start backend
start /B "" ".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000

:: Wait for backend to start
timeout /t 5 /nobreak >nul

:: Start frontend
cd /d C:\Users\suche\Documents\jarvis\frontend
start /B "" npm run dev

:: Wait for frontend to start
timeout /t 4 /nobreak >nul

:: Open as standalone app window (no tabs, no URL bar — like real JARVIS)
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:5173 --window-size=500,700 --window-position=900,100

echo JARVIS is online!
