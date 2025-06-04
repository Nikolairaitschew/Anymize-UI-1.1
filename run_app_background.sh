#!/bin/bash

# Anymize OCR App - Background Mode (Linux)
# =========================================
# This script runs the OCR app in background mode so the terminal can be closed

# Set environment variables if needed
# export NOCODB_BASE="your_nocodb_url"
# export NOCODB_TOKEN="your_token"
# export N8N_WEBHOOK="your_webhook_url"

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure logs directory exists
mkdir -p logs

# Kill ALL existing processes
echo -e "${BLUE}Checking for existing processes...${NC}"

# Method 1: Check PID file
if [ -f anymize.pid ]; then
    PID=$(cat anymize.pid)
    if ps -p $PID > /dev/null; then
        echo -e "${BLUE}Stopping existing process ($PID)...${NC}"
        kill -9 $PID
        sleep 2
        echo -e "${GREEN}Process $PID terminated.${NC}"
    fi
    # Remove old PID file regardless of whether process was found
    rm -f anymize.pid
fi

# Method 2: Find any Python processes running enhanced_ocr_app.py
echo -e "${BLUE}Checking for any other Python processes running the app...${NC}"
PYTHON_PIDS=$(ps aux | grep "[p]ython.*anymize" | awk '{print $2}')
if [ ! -z "$PYTHON_PIDS" ]; then
    echo -e "${RED}Found additional running processes: $PYTHON_PIDS${NC}"
    for pid in $PYTHON_PIDS; do
        echo -e "${BLUE}Killing process $pid...${NC}"
        kill -9 $pid
    done
    echo -e "${GREEN}All old processes terminated.${NC}"
    sleep 2
fi

# Double check nothing is running on port 8000
PORT_PID=$(lsof -t -i:8000 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo -e "${RED}Found process using port 8000: $PORT_PID${NC}"
    echo -e "${BLUE}Killing process on port 8000...${NC}"
    kill -9 $PORT_PID
    sleep 2
fi

# Start the app in background mode
echo -e "${BLUE}===================================${NC}"
echo -e "${BLUE}Anymize OCR App - Background Mode (Linux)${NC}"
echo -e "${BLUE}===================================${NC}"
echo -e "${GREEN}Starting Anymize OCR App in background...${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Start with nohup to keep it running after terminal closes
# Using the new run.py script which properly handles all imports
nohup venv/bin/python run.py > logs/anymize_app.log 2>&1 &

# Save the process ID
PID=$!
echo $PID > anymize.pid
echo -e "${GREEN}Process ID: $PID${NC}"
echo ""
echo -e "${GREEN}The application has been started in the background!${NC}"
echo -e "- The app is accessible at: ${BLUE}http://0.0.0.0:8000${NC} or ${BLUE}http://localhost:8000${NC}"
echo -e "- Logs are saved in ${BLUE}logs/anymize_app.log${NC}"
echo -e "- To stop the app, run ${BLUE}'./stop_app.sh'${NC} or ${BLUE}'kill $PID'${NC}"
echo ""

# Try to open browser
read -p "Open browser? (y/n): " -n 1 -r
echo    # Move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Attempting to open browser..."
    
    # Check available browser commands and try each one
    BROWSER_OPENED=0
    
    # Try xdg-open (standard way on Linux)
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8000 && BROWSER_OPENED=1
    fi
    
    # If xdg-open failed, try other common browsers
    if [ $BROWSER_OPENED -eq 0 ]; then
        for browser in google-chrome chromium-browser firefox opera brave-browser; do
            if command -v $browser &> /dev/null; then
                $browser http://localhost:8000 &> /dev/null &
                BROWSER_OPENED=1
                break
            fi
        done
    fi
    
    # If we still couldn't open a browser
    if [ $BROWSER_OPENED -eq 0 ]; then
        echo -e "${BLUE}Could not automatically open browser.${NC}"
        echo -e "${BLUE}Please manually open ${GREEN}http://localhost:8000${BLUE} in your browser.${NC}"
    else
        echo -e "${BLUE}Browser opened to ${GREEN}http://localhost:8000${NC}"
    fi
else
    echo -e "${BLUE}Please manually open ${GREEN}http://localhost:8000${BLUE} in your browser when ready.${NC}"
fi

# Done
echo ""
echo -e "${BLUE}Application is running in the background.${NC}"
echo -e "${BLUE}Press Ctrl+C to exit this script (the app will continue running).${NC}"
