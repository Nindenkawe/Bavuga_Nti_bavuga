#!/bin/bash

# Default to production mode
DEV_MODE=false

# Check for --dev flag
if [ "$1" == "--dev" ]; then
    DEV_MODE=true
fi

# Run the application
if [ "$DEV_MODE" == true ]; then
    echo "Starting in development mode..."
    python3 main.py --dev
else
    echo "Starting in production mode..."
    python3 main.py
fi
