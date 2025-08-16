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
        --help)
        echo -e "${C_CYAN}Usage: ./start.sh [--dev] [--debug] [--help]${C_RESET}"
        echo -e "  ${C_YELLOW}--dev${C_RESET}      Run in DEVELOPMENT mode (uses local JSON DB, Gemini for audio)."
        echo -e "  ${C_YELLOW}--debug${C_RESET}    Enable verbose DEBUG logging, including underlying API calls."
        echo -e "  ${C_YELLOW}--help${C_RESET}     Display this help message."
        exit 0
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
echo -e "${C_BLUE}=========================================${C_RESET}"
echo -e "${C_BLUE}---      Bavuga Ntibavuga Server      ---${C_RESET}"
echo -e "${C_BLUE}=========================================${C_RESET}"
echo

if [ "$DEV_MODE" == true ]; then
    echo -e "${C_GREEN}Mode:${C_RESET}      ${C_YELLOW}DEVELOPMENT${C_RESET}"
    echo -e "${C_GREEN}Database:${C_RESET}  Using local ${C_CYAN}dev_db.json${C_RESET} file."
    echo -e "${C_GREEN}Audio Proc:${C_RESET} Using ${C_CYAN}Gemini API${C_RESET} for Speech-to-Text and Text-to-Speech."
else
    echo -e "${C_GREEN}Mode:${C_RESET}      ${C_RED}PRODUCTION${C_RESET}"
    echo -e "${C_GREEN}Database:${C_RESET}  Using ${C_CYAN}MongoDB via Docker${C_RESET}. Make sure Docker is running."
    echo -e "${C_GREEN}Audio Proc:${C_RESET} Using ${C_CYAN}Google Cloud APIs${C_RESET}. (Ensure GOOGLE_CLOUD_PROJECT is set)."
fi

if [ "$DEBUG_MODE" == true ]; then
    echo
    echo -e "${C_YELLOW}DEBUG mode is ENABLED.${C_RESET}"
    echo -e "Expect ${C_RED}EXTREMELY VERBOSE${C_RESET} logging."
    echo -e "This will show detailed logs from:"
    echo -e "  - ${C_CYAN}genai_processors${C_RESET}: The core library interacting with the Gemini API."
    echo -e "  - ${C_CYAN}httpx${C_RESET}: The underlying HTTP client making the web requests."
    echo -e "  - ${C_CYAN}google.api_core${C_RESET}: The Google Cloud client library."
    echo -e "This is useful for deep debugging of API calls and model interactions."
fi

echo
echo -e "${C_GREEN}Running command:${C_RESET} ${C_CYAN}$CMD${C_RESET}"
echo -e "${C_BLUE}-----------------------------------------${C_RESET}"
echo

# --- Run the application ---
# The trap will execute on EXIT, which includes Ctrl+C
trap "echo; echo -e \"${C_RED}-----------------------------------------\"; echo -e \"${C_RED}Application stopped.${C_RESET}\"; echo;" EXIT

$CMD
