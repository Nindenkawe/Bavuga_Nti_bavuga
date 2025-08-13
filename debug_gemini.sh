#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# The log file for mitmproxy
LOG_FILE="gemini_api_trace.log"

# --- Prerequisite Check ---
echo "STEP 0: Checking for mitmproxy..."
if ! command -v mitmproxy &> /dev/null; then
    echo "Error: 'mitmproxy' is not installed."
    echo "Please install it by running: pip install mitmproxy"
    exit 1
fi
echo "mitmproxy found."
echo

# --- Instructions ---
echo "--- Gemini API Debug Trace --- "
echo
echo "This script will start a proxy to capture all communication"
echo "between this application and the Gemini API."
echo
echo "- The raw request and response data will be saved to: $LOG_FILE"
_echi "- To view the live traffic, open a new terminal and run: mitmweb"
echo

# --- Start mitmproxy ---
echo "STEP 1: Starting mitmproxy in the background..."
# The --set stream_large_bodies=1 option is important to see the full request/response
mitmproxy --mode transparent --showhost --set stream_large_bodies=1 -w "$LOG_FILE" "~d generativelanguage.googleapis.com" & 
Mitmproxy_PID=$!
echo "mitmproxy started with PID: $Mitmproxy_PID"
echo

# --- Run FastAPI with Proxy ---
echo "STEP 2: Starting FastAPI application with proxy enabled..."
# Set the proxy for the application
export HTTPS_PROXY=http://127.0.0.1:8080
# Run the app in dev mode
./run.sh --dev

# --- Cleanup ---
echo "Cleaning up..."
kill $Mitmproxy_PID

