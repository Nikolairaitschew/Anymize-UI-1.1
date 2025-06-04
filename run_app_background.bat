@echo off
echo ===================================
echo Anymize OCR App - Background Mode
echo ===================================

:: Die folgenden Zeilen ermöglichen es, die App im Hintergrund auszuführen,
:: sodass sie nicht beendet wird, wenn das Terminal-Fenster geschlossen wird.

:: Ensure logs directory exists
if not exist logs mkdir logs

:: Kill any existing processes
echo Checking for existing processes...

:: Method 1: Check PID file
if exist anymize.pid (
    set /p PID=<anymize.pid
    echo Found PID file with process ID: %PID%
    taskkill /F /PID %PID% 2>nul
    del anymize.pid
    echo Removed existing PID file
)

:: Method 2: Kill any process using port 8000
echo Checking for processes using port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Found process using port 8000: %%a
    taskkill /F /PID %%a 2>nul
)

:: Method 3: Kill any Python processes running our app
echo Checking for Python processes running enhanced_ocr_app...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /i "anymize"') do (
    echo Found Python process: %%a
    taskkill /F /PID %%a 2>nul
)

:: Wait a moment to ensure processes are stopped
timeout /t 2 > nul

:: Setze den Pfad zur Python-Installation - anpassen wenn nötig
set PYTHON_PATH=python

:: Prüfe, ob Python verfügbar ist
%PYTHON_PATH% --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python nicht gefunden! Bitte überprüfe die Python-Installation.
    echo Eventuell musst du den PYTHON_PATH in diesem Script anpassen.
    pause
    exit /b 1
)

:: Starte die Anwendung ohne Konsolenfenster (versteckt)
echo Starte Anymize OCR App im Hintergrund...
start "Anymize OCR Background" /b %PYTHON_PATH% run.py

:: Gib dem Benutzer Feedback
echo.
echo Die Anwendung wurde im Hintergrund gestartet!
echo - Schließe dieses Fenster, die App läuft weiter.
echo - Die App ist erreichbar unter: http://0.0.0.0:8000 oder http://localhost:8000
echo - Um die App zu beenden, nutze den Task-Manager und beende den Python-Prozess.
echo.

:: Option, um den Browser zu öffnen
set /p OPEN_BROWSER="Browser öffnen? (j/n): "
if /i "%OPEN_BROWSER%"=="j" (
    start http://localhost:8000
)

pause
