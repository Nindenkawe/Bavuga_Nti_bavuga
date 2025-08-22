#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# The Project ID for your Google Cloud project is read from the first argument.
# The Project ID for your Google Cloud project.
PROJECT_ID="bavuga-ntibavuga-468809"
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

# --- Prerequisite Check ---
echo "STEP 0: Checking for prerequisites..."
if ! command -v gcloud &> /dev/null; then
    echo "Error: 'gcloud' command not found. Please install the Google Cloud SDK."
    exit 1
fi

# A more robust check for gcloud login status.
if [ -z "$(gcloud auth list --filter=status:ACTIVE --format='value(account)')" ]; then
    echo "You are not logged into gcloud. Please run 'gcloud auth login' and 'gcloud auth application-default login' first."
    exit 1
else
    echo "gcloud authentication found."
fi

# --- Step 1: Set the active project ---
echo "STEP 1: Setting active project to '$PROJECT_ID'"
gcloud config set project "$PROJECT_ID"
echo "Project set successfully."

# --- Step 2: Enable required APIs ---
echo "STEP 2: Enabling required APIs (Vertex AI, Speech-to-Text, and Text-to-Speech)..."
gcloud services enable aiplatform.googleapis.com speech.googleapis.com texttospeech.googleapis.com
echo "APIs enabled successfully."

# --- Step 3: Create the service account ---
echo "STEP 3: Creating service account '$SERVICE_ACCOUNT_NAME'"
# Check if the service account already exists to avoid errors.
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="$PROJECT_ID" &>/dev/null; then
  echo "Service account '$SERVICE_ACCOUNT_NAME' already exists. Skipping creation."
else
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="$DISPLAY_NAME" \
    --project="$PROJECT_ID"
  echo "Service account created successfully."
fi

# --- Step 4: Grant IAM roles to the service account ---
echo "STEP 4: Granting necessary IAM roles..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/aiplatform.user" \
  --quiet
echo "Granted 'Vertex AI User' role."

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/speech.client" \
  --quiet
echo "Granted 'Cloud Speech Client' role."

# --- Step 5: Create and download the service account key ---
echo "STEP 5: Creating and downloading service account key..."
if [ -f "$KEY_FILE" ]; then
    echo "Key file '$KEY_FILE' already exists. Skipping key creation."
else
    gcloud iam service-accounts keys create "$KEY_FILE" \
      --iam-account="${SERVICE_ACCOUNT_EMAIL}" \
      --project="$PROJECT_ID"
    echo "Key file '$KEY_FILE' created successfully."
fi

echo
echo "--- Setup Complete! ---"
echo "The '$KEY_FILE' has been created and/or verified in your project directory."
