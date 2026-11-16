@echo off
rem Build dist\YouLiDownloader\YouLiDownloader.exe with PyInstaller.
rem Uses a separate .venv-build with only PySide6-Essentials, so the package
rem does not pull in QtWebEngine (~200 MB) from the full PySide6 in .venv.
setlocal
cd /d "%~dp0"

if not exist ".venv-build\Scripts\python.exe" (
    echo Creating build environment .venv-build ...
    where uv >nul 2>nul
    if not errorlevel 1 (
        uv venv --python 3.13 .venv-build || goto :fail
        uv pip install --python .venv-build\Scripts\python.exe -r requirements-dev.txt || goto :fail
    ) else (
        py -3 -m venv .venv-build || goto :fail
        .venv-build\Scripts\python.exe -m pip install -r requirements-dev.txt || goto :fail
    )
)

set PYTHONUTF8=1
".venv-build\Scripts\python.exe" tools\build.py || goto :fail
echo.
pause
exit /b 0

:fail
echo.
echo Build failed. See the messages above.
pause
exit /b 1
