@echo off
echo ===================================
echo Anymize OCR App - Stop Script
echo ===================================

echo Beende die Anymize OCR App...

:: Finde den Python-Prozess, der die enhanced_ocr_app.py au00fcsfu00fchrt
echo Suche laufende Python-Prozesse fu00fcr die Anymize App...

:: Tasklist mit Filter fu00fcr pythonw und enhanced_ocr_app.py
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq pythonw.exe" /fo csv /nh ^| findstr /i "pythonw.exe"') do (
    set "PID=%%~i"
    
    :: Entferne Fu00fchrungszeichen aus PID
    set "PID=!PID:"=!"
    
    echo Gefundener Python-Prozess mit PID: !PID!
    
    :: Beende den Prozess
    taskkill /pid !PID! /f
    
    if !ERRORLEVEL! == 0 (
        echo Prozess erfolgreich beendet.
    ) else (
        echo Fehler beim Beenden des Prozesses. Bitte manuell im Task-Manager beenden.
    )
)

echo.
echo Falls die App weiterhin lu00e4uft, bitte im Task-Manager
echo alle "pythonw.exe"-Prozesse manuell beenden.
echo.

pause
