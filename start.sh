#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- ANSI Color Codes ---
C_BLUE="\033[1;34m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_CYAN="\033[1;36m"
C_RESET="\033[0m"

# --- Default settings ---
export DEV_MODE=false
export DEBUG_MODE=false

# --- Parse command-line arguments ---
for arg in "$@"
do
    case $arg in
        --dev)
        export DEV_MODE=true
        shift
        ;;
        --debug)
        export DEBUG_MODE=true
        shift
        ;;
        --help)
        echo -e "${C_CYAN}Usage: ./start.sh [--dev] [--debug] [--help]${C_RESET}"
        echo -e "  ${C_YELLOW}--dev${C_RESET}      Run in DEVELOPMENT mode (enables auto-reload)."
        echo -e "  ${C_YELLOW}--debug${C_RESET}    Enable verbose DEBUG logging."
        echo -e "  ${C_YELLOW}--help${C_RESET}     Display this help message."
        exit 0
        ;;
    esac
done

# --- Create logs directory ---
LOG_DIR="logs"
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/run_$(date +%Y-%m-%d_%H-%M-%S).log"

# --- Build the command ---
CMD="uvicorn main:app --host 0.0.0.0 --port 8080"
if [ "$DEV_MODE" == true ]; then
    CMD="$CMD --reload"
fi

if [ "$DEBUG_MODE" == true ]; then
    CMD="$CMD --log-level debug"
fi

# --- Display information to the user ---
echo -e "${C_BLUE}=========================================${C_RESET}"
echo -e "${C_BLUE}---      Bavuga Ntibavuga Server      ---${C_RESET}"
echo -e "${C_BLUE}=========================================${C_RESET}"
echo

if [ "$DEV_MODE" == true ]; then
    echo -e "${C_GREEN}Mode:${C_RESET}      ${C_YELLOW}DEVELOPMENT${C_RESET}"
    echo -e "${C_GREEN}Auto-reload:${C_RESET} ${C_GREEN}ENABLED${C_RESET}"
else
    echo -e "${C_GREEN}Mode:${C_RESET}      ${C_RED}PRODUCTION${C_RESET}"
fi

echo

if [ "$DEBUG_MODE" == true ]; then
    echo -e "${C_YELLOW}DEBUG mode is ENABLED.${C_RESET}"
    echo -e "A detailed log of this session will be saved to: ${C_CYAN}${LOG_FILE}${C_RESET}"
    echo -e "You can monitor the log in real-time with: ${C_YELLOW}tail -f ${LOG_FILE}${C_RESET}"
else
    echo -e "${C_YELLOW}For detailed logs, run with the --debug flag.${C_RESET}"
fi

echo
echo -e "${C_GREEN}Running command:${C_RESET} ${C_CYAN}$CMD${C_RESET}"
echo -e "${C_BLUE}-----------------------------------------${C_RESET}"
echo

# --- Run the application ---
# The trap will execute on EXIT, which includes Ctrl+C
trap "echo; echo -e \"${C_RED}-----------------------------------------\"; echo -e \"${C_RED}Application stopped.${C_RESET}\"; echo;" EXIT

# Use tee to send output to both the console and the log file
# Use stdbuf to disable output buffering to ensure real-time logging
if [ "$DEBUG_MODE" == true ]; then
    # In debug mode, we pipe all output (stdout & stderr) to tee, which logs to a file and prints to the console.
    # stdbuf -oL sets the output stream to be line-buffered.
    stdbuf -oL -eL $CMD 2>&1 | tee "$LOG_FILE"
else
    # In normal mode, just run the command.
    $CMD
fi

