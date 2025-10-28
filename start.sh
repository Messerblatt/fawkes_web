#!/bin/bash

# Fawkes Web Application Startup Script
# This script starts the application using Gunicorn for production

set -e

echo "============================================"
echo "Starting Fawkes Web Application"
echo "============================================"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if required directories exist
if [ ! -d "images" ]; then
    echo "Creating images directory..."
    mkdir -p images
fi

if [ ! -d "fawkes" ]; then
    echo "ERROR: Fawkes directory not found!"
    echo "Please clone the Fawkes repository into the 'fawkes' directory"
    exit 1
fi

# Check if Gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    echo "ERROR: Gunicorn is not installed!"
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Set environment variables
export FLASK_ENV=production
export SECRET_KEY=${SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_hex(32))')}

echo "Configuration:"
echo "  - Port: 5000"
echo "  - Workers: 1 (eventlet)"
echo "  - Environment: production"
echo ""

# Start Gunicorn
echo "Starting Gunicorn server..."
gunicorn --config gunicorn_config.py wsgi:app

# If the script exits, show error
echo ""
echo "Server stopped"
