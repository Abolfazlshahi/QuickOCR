@echo off
setlocal
cd /d "%~dp0"
title QuickOCR Uninstaller

echo Stopping QuickOCR if running...
taskkill /F /IM QuickOCR.exe >nul 2>nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*QuickOCR*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Removing shortcuts...
powershell -NoProfile -Command "$paths = @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'QuickOCR.lnk'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'QuickOCR.lnk'), (Join-Path ([Environment]::GetFolderPath('Startup')) 'QuickOCR.lnk')); foreach ($p in $paths) { if (Test-Path $p) { Remove-Item $p -Force; Write-Host 'Removed:' $p } }"

echo.
echo Shortcuts and running instances removed. You may delete this folder to completely uninstall QuickOCR.
pause
