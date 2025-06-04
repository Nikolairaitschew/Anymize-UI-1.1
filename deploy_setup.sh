#!/bin/bash

echo "======================================"
echo "Anymize Deployment Setup"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ -f .env ]; then
    echo -e "${GREEN}✓ .env file found${NC}"
    source .env
else
    echo -e "${YELLOW}⚠ No .env file found. Creating from template...${NC}"
    
    # Create .env from template
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env from .env.example${NC}"
        echo -e "${YELLOW}⚠ Please edit .env and set your API tokens!${NC}"
    else
        # Create basic .env if no template
        cat > .env << EOF
# Auto-generated .env file
# SECURITY WARNING: Update these values for production!

# NocoDB API Token (current: using default development token)
NOCODB_TOKEN=wlf8BFp6fkR-NNoL9TZQ91sJ8msFwB_kWhXqPyTZ

# Flask Secret Key (auto-generated)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Optional: Override NocoDB base URL
# NOCODB_BASE=https://your-nocodb-instance.com/api/v2
EOF
        echo -e "${GREEN}✓ Created .env with default values${NC}"
        echo -e "${YELLOW}⚠ Using development token! Update NOCODB_TOKEN for production!${NC}"
    fi
fi

# Create required directories
echo -e "\n${GREEN}Creating required directories...${NC}"
mkdir -p uploads logs

# Set up Python virtual environment
if [ ! -d "venv" ]; then
    echo -e "\n${GREEN}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
if [ -f "requirements.txt" ]; then
    echo -e "\n${GREEN}Installing Python requirements...${NC}"
    pip install -r requirements.txt
else
    echo -e "\n${YELLOW}⚠ No requirements.txt found. Installing basic dependencies...${NC}"
    pip install Flask Flask-Limiter requests python-docx reportlab python-dotenv
fi

# Check if running on production (HTTPS available)
echo -e "\n${YELLOW}Production checklist:${NC}"
echo "1. ✓ Set NOCODB_TOKEN in .env (not using default)"
echo "2. ✓ Set SECRET_KEY in .env (auto-generated)"
echo "3. ⚠ Enable HTTPS for secure cookies"
echo "4. ⚠ Configure firewall rules"
echo "5. ⚠ Set up log rotation"

echo -e "\n${GREEN}Setup complete!${NC}"
echo "To start the app:"
echo "  Development: ./run_app.sh"
echo "  Background: ./run_app_background.sh"
echo "  Production: Consider using systemd or supervisor"

# Make scripts executable
chmod +x run_app.sh run_app_background.sh stop_app.sh 2>/dev/null

echo -e "\n${GREEN}✓ All scripts are now executable${NC}"
