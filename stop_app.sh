#!/bin/bash

# ===================================
# Anymize OCR App - Stop Script (Linux)
# ===================================

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stoppe Anymize OCR App...${NC}"

# Methode 1: Prüfe, ob die PID-Datei existiert
if [ -f anymize.pid ]; then
    # Lese die PID aus der Datei
    PID=$(cat anymize.pid)
    
    # Prüfe, ob der Prozess noch läuft
    if ps -p $PID > /dev/null; then
        echo -e "${BLUE}Beende Prozess mit PID: $PID${NC}"
        kill $PID
        
        # Kurz warten und prüfen, ob der Prozess beendet wurde
        sleep 2
        if ! ps -p $PID > /dev/null; then
            echo -e "${GREEN}Prozess erfolgreich beendet.${NC}"
        else
            echo -e "${RED}Prozess läuft noch. Versuche erzwungene Beendigung...${NC}"
            kill -9 $PID
            
            # Erneut prüfen
            sleep 1
            if ! ps -p $PID > /dev/null; then
                echo -e "${GREEN}Prozess erfolgreich beendet.${NC}"
            else
                echo -e "${RED}Fehler beim Beenden des Prozesses.${NC}"
            fi
        fi
    else
        echo -e "${RED}Kein laufender Prozess mit PID $PID gefunden.${NC}"
    fi
    
    # Lösche die PID-Datei
    rm anymize.pid
    echo -e "${GREEN}PID-Datei entfernt.${NC}"
else
    echo -e "${RED}Keine anymize.pid Datei gefunden.${NC}"
fi

# Methode 2: Suche nach Prozessen, die run.py oder enhanced_ocr_app.py ausführen
echo -e "${BLUE}Suche nach weiteren laufenden Anymize-Prozessen...${NC}"

# Finde alle Python-Prozesse, die entweder run.py oder Anymize ausführen
PYTHON_PIDS=$(ps aux | grep python | grep -E 'run\.py|anymize|enhanced_ocr_app\.py' | grep -v grep | awk '{print $2}')

if [ ! -z "$PYTHON_PIDS" ]; then
    echo -e "${RED}Gefundene Prozesse: $PYTHON_PIDS${NC}"
    for pid in $PYTHON_PIDS; do
        echo -e "${BLUE}Beende Prozess mit PID: $pid${NC}"
        kill -9 $pid
    done
    sleep 1
    echo -e "${GREEN}Alle Prozesse beendet.${NC}"
fi

# Methode 3: Prüfe, ob Port 8000 noch belegt ist
PORT_PID=$(lsof -i:8000 -t 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo -e "${RED}Port 8000 ist noch belegt von Prozess: $PORT_PID${NC}"
    echo -e "${BLUE}Beende Prozess...${NC}"
    kill -9 $PORT_PID
    sleep 1
    echo -e "${GREEN}Prozess beendet.${NC}"
fi

echo -e "${GREEN}Fertig.${NC}"
