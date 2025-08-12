#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# The Project ID for your Google Cloud project.
PROJECT_ID="$1"
# The name for your new service account.
SERVICE_ACCOUNT_NAME="bavuga-app-service-account"
# The name of the key file to be created.
KEY_FILE="google-credentials.json"
# A user-friendly name for the service account.
DISPLAY_NAME="Bavuga App Service Account"

# --- Validation ---
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No Project ID provided."
  echo "Usage: ./setup_gcloud.sh <YOUR_PROJECT_ID>"
  exit 1
fi

# Construct the full email address for the service account.
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "--- Google Cloud Setup for Bavuga App ---"
echo

# --- Prerequisite Check ---
echo "STEP 0: Checking for gcloud authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "You are not logged into gcloud. Please run 'gcloud auth login' and 'gcloud auth application-default login' first."
    exit 1
else
    echo "gcloud authentication found."
fi
echo

# --- Step 1: Set the active project ---
echo "STEP 1: Setting active project to '$PROJECT_ID'ப்பான"
gcloud config set project "$PROJECT_ID"
echo "Project set successfully."
echo

# --- Step 2: Enable required APIs ---
echo "STEP 2: Enabling required APIs (Speech-to-Text and Text-to-Speech)..."
gcloud services enable speech.googleapis.com texttospeech.googleapis.com
echo "APIs enabled successfully."
echo

# --- Step 3: Create the service account ---
echo "STEP 3: Creating service account '$SERVICE_ACCOUNT_NAME'ப்பான"
# Check if the service account already exists to avoid errors.
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="$PROJECT_ID" &>/dev/null; then
  echo "Service account '$SERVICE_ACCOUNT_NAME' already exists. Skipping creation."
else
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="$DISPLAY_NAME" \
    --project="$PROJECT_ID"
  echo "Service account created successfully."
fi
echo

# --- Step 4: Grant IAM roles to the service account ---
echo "STEP 4: Granting necessary IAM roles..."
# Role for Text-to-Speech
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/texttospeech.user" \
  --quiet
echo "Granted 'Cloud Text-to-Speech User' role."

# Role for Speech-to-Text
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/speech.user" \
  --quiet
echo "Granted 'Cloud Speech-to-Text User' role."
echo

# --- Step 5: Create and download the service account key ---
echo "STEP 5: Creating and downloading service account key..."
gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account="${SERVICE_ACCOUNT_EMAIL}" \
  --project="$PROJECT_ID"
echo "Key file '$KEY_FILE' created successfully."
echo

# --- Completion ---
echo "--- Setup Complete! ---"
echo "The '$KEY_FILE' has been created in your project directory."
echo "You can now run 'docker-compose up --build -d' to start the application."
