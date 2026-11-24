@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title QuickOCR Setup

echo ============================================
echo   QuickOCR Installer (OCRia-nano-1)
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.10+ not found in PATH. Please install Python first.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating virtual environment...
    python -m venv ".venv"
    if errorlevel 1 goto :fail
) else (
    echo [1/5] Virtual environment already exists.
)

echo [2/5] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

set "LITEPARSE_MODEL_DIR=%~dp0models"
if not exist "models\ocria-nano\det.onnx" (
    echo [3/5] Downloading default ocria-nano model...
    ".venv\Scripts\lit.exe" models pull ocria-nano
    if errorlevel 1 goto :fail
) else (
    echo [3/5] Bundled ocria-nano model verified offline.
)

if not exist "runtime\python311.dll" (
    echo [4/5] Fetching non-MSIX Python 3.11 embeddable host...
    mkdir "runtime" >nul 2>nul
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'runtime\py311.zip' -UseBasicParsing; Expand-Archive -Path 'runtime\py311.zip' -DestinationPath 'runtime' -Force; Remove-Item 'runtime\py311.zip'"
    > "runtime\python311._pth" (
        echo python311.zip
        echo .
        echo ..
        echo ..\.venv\Lib\site-packages
        echo import site
    )
) else (
    echo [4/5] Non-MSIX host runtime verified.
)

echo [5/5] Building QuickOCR.exe and creating shortcuts...
set "CSC=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if exist "!CSC!" (
    "!CSC!" /nologo /target:winexe /platform:x64 /win32icon:"icon.ico" /reference:System.Windows.Forms.dll /out:"QuickOCR.exe" "launcher.cs" >nul 2>nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $startm = [Environment]::GetFolderPath('Programs'); foreach ($dir in @($desk, $startm, '%~dp0')) { $s = $ws.CreateShortcut((Join-Path $dir 'QuickOCR.lnk')); if (Test-Path '%~dp0QuickOCR.exe') { $s.TargetPath = '%~dp0QuickOCR.exe'; $s.Arguments = ''; $s.IconLocation = '%~dp0QuickOCR.exe,0' } else { $s.TargetPath = '%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments = '\"%~dp0app.py\"'; $s.IconLocation = '%~dp0icon.ico,0' }; $s.WorkingDirectory = '%~dp0'; $s.Save() }"

echo.
echo [DONE] QuickOCR installed cleanly!
echo Starting QuickOCR in the system tray...
if exist "QuickOCR.exe" (
    start "" "QuickOCR.exe"
) else (
    start "" ".venv\Scripts\pythonw.exe" "app.py"
)
exit /b 0

:fail
echo.
echo [FAILED] Installation encountered an error.
pause
exit /b 1
