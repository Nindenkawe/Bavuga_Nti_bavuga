#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Instructions ---
echo "--- Gemini API Debug Trace --- "
echo
echo "This script will run the application in development mode with detailed logging."
echo "Gemini API requests and responses will be logged to the console."
echo

# --- Run FastAPI ---
echo "STEP 1: Starting FastAPI application in debug mode..."
# The --debug flag will enable verbose logging in main.py
./run.sh --dev --debug

echo "Script finished."
