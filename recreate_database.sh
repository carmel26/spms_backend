#!/bin/bash

# Database Recreation Script for SPMS
# This script will completely recreate the database with fresh UUID-based schema
# Author: Auto-generated
# Date: $(date +"%Y-%m-%d")

set -e  # Exit on any error

echo "============================================"
echo "SPMS Database Recreation Script"
echo "============================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found!${NC}"
    echo "Please create a virtual environment first: python -m venv venv"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Backup existing database if it exists
if [ -f "db.sqlite3" ]; then
    BACKUP_NAME="db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}Backing up existing database to $BACKUP_NAME...${NC}"
    cp db.sqlite3 "$BACKUP_NAME"
    echo -e "${GREEN}✓ Backup created${NC}"
fi

# Remove existing database
echo -e "${YELLOW}Removing existing database...${NC}"
rm -f db.sqlite3
rm -f db.sqlite3-shm
rm -f db.sqlite3-wal
echo -e "${GREEN}✓ Database removed${NC}"

# Remove __pycache__ and .pyc files
echo -e "${YELLOW}Cleaning Python cache files...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Cache cleaned${NC}"

# Run migrations to create tables
echo -e "${YELLOW}Creating database schema...${NC}"
python manage.py migrate --run-syncdb
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database schema created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create database schema${NC}"
    exit 1
fi

# Create superuser (optional - commented out by default)
echo ""
echo -e "${YELLOW}Creating superuser...${NC}"
echo "You can create a superuser now or skip this step."
echo "To skip, press Ctrl+C and run manually later: python manage.py createsuperuser"
echo ""
python manage.py createsuperuser || echo -e "${YELLOW}Superuser creation skipped${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Database recreation completed successfully!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Next steps:"
echo "1. Run the development server: python manage.py runserver"
echo "2. Or run the setup admin script: python setup_admin.py"
echo "3. Or restore data from backup if needed"
echo ""
