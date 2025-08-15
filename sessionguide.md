# Welcome to the Bavuga Ntibavuga Developer's Guide

Welcome to the guide for **Bavuga Ntibavuga**, a dynamic Kinyarwanda language game powered by Google's Generative AI. This project showcases a modern, modular application structure and the power of Gemini for creative, multimodal interactions.

This guide will walk you through the project's architecture, explaining how to get the app running and how its core components work together.

### The Core Architecture: Processors

The application's logic is no longer in a single file but is organized into a `processors` directory. This makes the code cleaner, more modular, and easier to maintain.

*   `ChallengeGeneratorProcessor`: The creative heart of the game. It crafts the prompts for each game mode (Story, Riddles, etc.) and gets the challenges from the Gemini API.
*   `AnswerEvaluatorProcessor`: The judge. It takes the user's answer and asks Gemini to evaluate if it's correct.
*   `Audio Processors`: A set of speech-to-text and text-to-speech processors that handle all voice interactions, powered by Gemini in dev mode.

### Choose Your Mode

You have two paths for running this application:

1.  **Path A: The Gemini Dev Mode (Recommended for Quick Start)**
    *   **Goal:** Quickly test the UI, game logic, and live audio features.
    *   **Requirements:** Only a `GEMINI_API_KEY`.
    *   **Features:** Uses the powerful multimodal Gemini API for **everything**: game logic, live speech-to-text, and text-to-speech. It uses a simple JSON file for the riddle database. No Docker or billing is required.

2.  **Path B: The Full Production Mode**
    *   **Goal:** Deploy the complete, production-ready application.
    *   **Requirements:** Docker, a billing-enabled Google Cloud project, and API keys.
    *   **Features:** Uses a robust MongoDB database and is containerized with Docker for easy deployment. While architected to use dedicated Google Cloud services for audio, it currently uses the Gemini audio processors as a reliable fallback.

Ready? Let's begin!

-----

## 1. The First Step: Configuring Your Environment

No matter which path you choose, you need to set up your secret keys. The application loads these from a `.env` file.

**Action:** Create a file named `.env` in the project root. Paste the following and add your Gemini API key.

```dotenv
# .env file

# Required for all AI features. Get this from Google AI Studio.
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

# --- The variables below are only needed for the Production path ---

# Tells the app where to find the MongoDB database inside Docker.
MONGODB_URI="mongodb://database:27017"

# The name of the database to use.
DATABASE_NAME="language_app"

# Your Google Cloud Project ID (for the production setup script)
GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
```

-----

## 2. Path A: The Gemini-Powered Dev Mode

This is your playground for rapid development. You get the full-featured experience, including audio, with minimal setup.

### Your Mission:

1.  **Install Dependencies:**
    Open your terminal and run:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Launch the App:**
    Our `start.sh` script makes this easy. The `--dev` flag activates this special mode.
    ```bash
    # Make the script executable (you only need to do this once)
    chmod +x start.sh

    # Engage Gemini Dev Mode!
    ./start.sh --dev

    # To see the Gemini API requests and responses in real-time, use the --debug flag:
    ./start.sh --dev --debug
    ```

Your local server is now running at `http://localhost:2500`. You can now use the microphone to speak your answers and hear the AI's responses.

**How it Works:** In this mode, the application's `APIRouter` receives requests and delegates tasks to the appropriate processor. The `GameProcessor` uses the `ChallengeGeneratorProcessor` to create challenges and the `AnswerEvaluatorProcessor` to grade them. For audio, the `websocket_routes` stream audio to the `GeminiSpeechToTextProcessor` and get spoken responses from the `GeminiTextToSpeechProcessor`.

-----

## 3. Path B: The Full Production Experience with Docker

This path gives you a full, production-grade deployment using dedicated services.

### Your Mission:

1.  **Prerequisites:**
    *   You must have **Docker** and **Docker Compose** installed.
    *   You need a **Google Cloud project with billing enabled**.

2.  **Automated Cloud Setup:**
    We've created a script to handle the tedious parts of cloud setup.
    ```bash
    # Make it executable
    chmod +x setup_gcloud.sh

    # Run it with your Google Cloud Project ID
    ./setup_gcloud.sh YOUR_PROJECT_ID
    ```
    This script enables the correct APIs and creates a `google-credentials.json` file that your Docker container will use to authenticate.

3.  **Launch with Docker Compose:**
    This single command builds and runs your entire application stack (FastAPI app + MongoDB).
    ```bash
    docker-compose up --build -d
    ```
    Your application is now live at `http://localhost:2500` with all features enabled!

-----

## 4. Understanding the Magic: A Look Inside the Processors

The magic of the game lies in how we instruct the Gemini model. This is handled entirely within the **processors**.

---

### `ChallengeGeneratorProcessor`: The Creative Director

This processor is responsible for creating the content for every game mode. It uses different prompting strategies to get the desired output from Gemini.

*   **Story Mode:** It prompts Gemini to act as a storyteller, requesting a short story formatted as a JSON object. It then uses individual chapters of that story as context to generate new challenges.
*   **BavugaNtiBavuga Mode:** It uses a simple, direct prompt asking Gemini for a phrase and its Kinyarwanda translation.
*   **Sakwe Sakwe Mode (Riddles):** This demonstrates **Retrieval-Augmented Generation (RAG)**. The processor first reads real Kinyarwanda riddles from `riddles.json`. It then includes these examples in the prompt, guiding Gemini to generate a new, authentic-sounding riddle. This is also known as **few-shot prompting**.
*   **Image Mode:** This showcases Gemini's **multimodal** capabilities. The processor sends both an image file and a text prompt to the model, asking it to describe the image in two languages.

---

### `AnswerEvaluatorProcessor`: The Grader

This processor determines if a user's answer is correct. It sends a prompt to Gemini that includes the original challenge, the correct answer, and the user's submitted answer, and asks for a "Correct" or "Incorrect" judgment.

---

### Audio Processors (`stt_processor` & `tts_processor`)

These processors, defined in `processors/audio.py`, handle all voice interactions.

*   **Speech-to-Text (`stt_processor`):** In dev mode, this is a `GeminiSpeechToTextProcessor`. The application streams audio from the user's microphone over a WebSocket connection directly to this processor, which uses the Gemini API to get a live transcription.
*   **Text-to-Speech (`tts_processor`):** This is a `GeminiTextToSpeechProcessor`. When the AI needs to speak, the application sends the text to this processor, which returns audio data that can be played in the browser.

-----

## 5. Troubleshooting Common Issues

*   **`ModuleNotFoundError`:**
    *   **Solution:** You forgot to install the dependencies! Run `pip install -r requirements.txt`.

*   **`503 Service Unavailable` or Errors on `/get_challenge`:**
    *   **Solution:** This usually means your `GEMINI_API_KEY` is missing or invalid. Double-check your `.env` file.

*   **Audio buttons don't work:**
    *   **Solution:** This could be a browser permission issue (make sure you've allowed microphone access) or an invalid Gemini API key. Check the browser's developer console and the application logs for errors.

-----

Thank you for following this guide. Happy coding!
