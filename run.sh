#!/bin/bash

# Default modes
DEV_MODE=false
DEBUG_MODE=false

# Process command-line arguments
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

# Build the command to run the application
CMD="python3 main.py"
if [ "$DEV_MODE" == true ]; then
    CMD="$CMD --dev"
    echo "Starting in development mode..."
else
    echo "Starting in production mode..."
fi

if [ "$DEBUG_MODE" == true ]; then
    CMD="$CMD --debug"
    echo "Debug logging is enabled."
fi

# Run the application
eval $CMD