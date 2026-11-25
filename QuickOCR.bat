@echo off
cd /d "%~dp0"
if exist "%~dp0QuickOCR.exe" (
    start "" "%~dp0QuickOCR.exe" %*
) else if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py" %*
) else (
    start "" "%~dp0runtime\pythonw.exe" "%~dp0app.py" %*
)
