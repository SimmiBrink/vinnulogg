@echo off
chcp 65001 >nul
echo ================================================
echo   Vinnulogg - Windows 11 Activity Logger
echo ================================================
echo.
cd /d "%~dp0"
python activity_logger.py
pause
