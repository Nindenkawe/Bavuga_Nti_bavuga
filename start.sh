#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Default settings ---
DEV_MODE=false
DEBUG_MODE=false

# --- Parse command-line arguments ---
for arg in "$@"
do
    case $arg in
        --dev)
        DEV_MODE=true
        shift
        ;;
        --debug)
        DEBUG_MODE=true
        shift
        ;;
    esac
done

# --- Build the command ---
CMD="python3 main.py"
if [ "$DEV_MODE" == true ]; then
    CMD="$CMD --dev"
fi

if [ "$DEBUG_MODE" == true ]; then
    CMD="$CMD --debug"
fi

# --- Display information to the user ---
echo "--- Bavuga Ntibavuga ---"
echo

if [ "$DEV_MODE" == true ]; then
    echo "Starting in DEVELOPMENT mode."
    echo "Database: Using local dev_db.json file."
else
    echo "Starting in PRODUCTION mode."
    echo "Database: Using MongoDB via Docker."
    echo "Make sure Docker is running."
fi

if [ "$DEBUG_MODE" == true ]; then
    echo
    echo "DEBUG mode is ENABLED."
    echo "Gemini API requests and responses will be logged to the console."
fi

echo
echo "Running command: $CMD"
echo "----------------------------------------"
echo

# --- Run the application ---
$CMD

echo
echo "----------------------------------------"
echo "Application stopped."