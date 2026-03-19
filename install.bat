@echo off
chcp 65001 >nul
echo ================================================
echo   Vinnulogg - Uppsetning
echo ================================================
echo.

:: Athuga hvort Python sé til staðar
python --version >nul 2>&1
if errorlevel 1 (
    echo VILLA: Python finnst ekki!
    echo Sæktu Python á https://python.org og reyndu aftur.
    echo Gakktu úr skugga um að "Add Python to PATH" sé hakað við við uppsetningu.
    pause
    exit /b 1
)

echo Python fundinn:
python --version
echo.

echo Uppfaerir pip...
python -m pip install --upgrade pip --quiet

echo Setti upp pakka...
python -m pip install pywin32 psutil

echo.
echo ================================================
echo   Uppsetning lokið!
echo   Keyrðu run.bat til að ræsa Vinnulogg.
echo ================================================
pause
