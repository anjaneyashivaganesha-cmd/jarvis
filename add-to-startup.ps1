$startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$target = "C:\Users\suche\Documents\jarvis\start-jarvis.bat"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("$startup\JARVIS.lnk")
$sc.TargetPath = $target
$sc.WorkingDirectory = "C:\Users\suche\Documents\jarvis"
$sc.Description = "JARVIS AI Assistant"
$sc.WindowStyle = 7
$sc.Save()
Write-Output "JARVIS added to Windows Startup!"
