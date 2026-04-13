@echo off
title JARVIS
echo Starting JARVIS...
echo.

:: Start backend
cd /d C:\Users\suche\Documents\jarvis\backend
start "JARVIS Backend" cmd /k "C:\Users\suche\AppData\Local\Programs\Python\Python312\Scripts\uv.exe" run uvicorn app.main:app --port 8000

:: Wait for backend to start
timeout /t 4 /nobreak >nul

:: Start frontend
cd /d C:\Users\suche\Documents\jarvis\frontend
start "JARVIS Frontend" cmd /k "C:\Program Files\nodejs\npm.cmd" run dev

:: Wait for frontend to start
timeout /t 3 /nobreak >nul

:: Open as standalone app window (like Claude - no tabs, no URL bar)
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:5173 --window-size=500,700 --window-position=900,100

echo JARVIS is running!
echo Close this window when done.
