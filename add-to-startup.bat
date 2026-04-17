@echo off
:: Create shortcut in Windows Startup folder
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=C:\Users\suche\Documents\jarvis\start-jarvis.bat"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%STARTUP%\JARVIS.lnk'); $sc.TargetPath = '%TARGET%'; $sc.WorkingDirectory = 'C:\Users\suche\Documents\jarvis'; $sc.Description = 'JARVIS AI Assistant'; $sc.WindowStyle = 7; $sc.Save()"

echo JARVIS added to Windows Startup!
echo It will auto-launch when you turn on your laptop.
pause
