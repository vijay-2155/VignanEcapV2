#!/bin/bash
set -e

# Update package repositories (requires sudo privileges)
sudo apt-get update

# Install OS dependencies required for Playwright (if not already present)
sudo apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon-x11-0 \
    libgbm-dev \
    libpango1.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libxdamage1 \
    libxshmfence1

echo "Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing project dependencies..."
pip install -r requirements.txt

echo "Installing Playwright OS dependencies..."
# This installs system dependencies for Playwright (if supported on your distro)
playwright install-deps

echo "Installing Playwright browsers..."
playwright install

echo "Starting the FastAPI application with Uvicorn..."
uvicorn app:app_api --host 0.0.0.0 --port 5000 --log-level info