@echo off
rem One-click launcher: double-click to run YTB Downloader from source.
rem First run creates .venv and installs requirements (uses uv if available, else py/pip).
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [YTB Downloader] First run: creating Python environment, please wait...
    where uv >nul 2>nul
    if not errorlevel 1 (
        uv venv --python 3.13 .venv || goto :fail
        uv pip install --python .venv\Scripts\python.exe -r requirements.txt || goto :fail
    ) else (
        py -3 -m venv .venv || goto :fail
        .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
    )
)

rem pythonw = no console window
start "" ".venv\Scripts\pythonw.exe" run.pyw
exit /b 0

:fail
echo.
echo [YTB Downloader] Environment setup failed. See the messages above.
pause
exit /b 1
