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
    echo [1/4] Creating virtual environment...
    python -m venv ".venv"
    if errorlevel 1 goto :fail
) else (
    echo [1/4] Virtual environment already exists.
)

echo [2/4] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

set "LITEPARSE_MODEL_DIR=%~dp0models"
if not exist "models\ocria-nano\det.onnx" (
    echo [3/4] Downloading default ocria-nano model...
    ".venv\Scripts\lit.exe" models pull ocria-nano
    if errorlevel 1 goto :fail
) else (
    echo [3/4] Bundled ocria-nano model verified offline.
)

echo [4/4] Building launcher and creating shortcuts...
set "CSC=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if exist "!CSC!" (
    "!CSC!" /nologo /target:winexe /win32icon:"icon.ico" /reference:System.Windows.Forms.dll /out:"QuickOCR.exe" "launcher.cs" >nul 2>nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $startm = [Environment]::GetFolderPath('Programs'); foreach ($dir in @($desk, $startm)) { $s = $ws.CreateShortcut((Join-Path $dir 'QuickOCR.lnk')); if (Test-Path '%~dp0QuickOCR.exe') { $s.TargetPath = '%~dp0QuickOCR.exe'; $s.Arguments = '' } else { $s.TargetPath = '%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments = '\"%~dp0app.py\"' }; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0icon.ico'; $s.Save() }"

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
