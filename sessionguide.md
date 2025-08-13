# Welcome to the Bavuga Ntibavuga Developer's Guide

Hello, fellow developer! Welcome to the official guide for **Bavuga Ntibavuga**, a dynamic Kinyarwanda language game powered by Google's Generative AI. If you're excited about building smart, interactive applications that feel alive, you're in the right place.

This guide is your all-access pass. We'll show you how to get the app running and, more importantly, pull back the curtain to reveal how the magic works.

### Choose Your Adventure

You have two paths for running this application. Choose the one that fits your goal:

1.  **Path A: The Gemini Dev Mode**
    *   **Goal:** Quickly test the UI, game logic, and even live audio transcription.
    *   **Requirements:** Only a `GEMINI_API_KEY`.
    *   **Features:** Uses the powerful multimodal Gemini API for game logic and speech-to-text, with a simple JSON file for a database. No Docker, no billing required.

2.  **Path B: The Full Production Experience**
    *   **Goal:** Deploy the complete, production-ready application.
    *   **Requirements:** Docker, a billing-enabled Google Cloud project, and API keys.
    *   **Features:** Uses dedicated, high-performance Google Cloud APIs for audio and a robust MongoDB database, all managed by Docker.

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
```

-----

## 2. Path A: The Gemini-Powered Dev Mode

This is your playground for rapid development. You'll be amazed at what you can do with just a Gemini API key.

### Your Mission:

1.  **Install Dependencies:**
    Open your terminal and run:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Launch the App:**
    Our `run.sh` script makes this easy. The `--dev` flag activates this special mode.
    ```bash
    # Make the script executable (you only need to do this once)
    chmod +x run.sh

    # Engage Gemini Dev Mode!
    ./run.sh --dev
    ```

Your local server is now running at `http://localhost:2500`. You can now use the microphone in the app to speak your answers!

**How it Works:** In this mode, the app sends your recorded audio directly to the Gemini API for transcription. It's a live demonstration of multimodal AI in action!

**Note:** The Text-to-Speech feature is disabled in this mode because the Gemini API generates text, not audio. The app will function perfectly, but you won't hear the answers spoken back.

-----

## 3. Path B: The Full Production Experience with Docker

This path gives you a full, production-grade deployment using dedicated, high-performance Google Cloud services.

### Your Mission:

1.  **Prerequisites:**
    *   You must have **Docker** and **Docker Compose** installed.
    *   You need a **Google Cloud project with billing enabled** to use the dedicated audio APIs.

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
    This single command builds and runs your entire application stack.
    ```bash
    docker-compose up --build -d
    ```
    Your application is now live at `http://localhost:2500` with all features enabled!

-----

## 4. How Gemini is Used: A Look Under the Hood

This application uses the Gemini model for more than just simple tasks. It uses several techniques to get high-quality, reliable responses from the model. This is a process called **grounding**.

### Grounding Technique 1: Retrieval-Augmented Generation (RAG)

**RAG** is a technique where you provide the model with information to "ground" its response in reality. In our case, we use the `riddles.json` file to give the model examples of Kinyarwanda riddles.

*   **How it works:** When generating a new riddle, the application retrieves a few random examples from `riddles.json` and includes them in the prompt. This is also known as **few-shot prompting**.

*   **Code Snippet (`main.py`):**
    ```python
    if challenge_type == "gusakuza":
        prompt = "Generate a Kinyarwanda riddle (igisakuzo). The response should be in the format 'riddle|answer'."
        if IBISAKUZO_EXAMPLES:
            # Retrieve examples from riddles.json
            examples = random.sample(IBISAKUZO_EXAMPLES, min(len(IBISAKUZO_EXAMPLES), 3))
            # Augment the prompt with the examples
            example_text = "\n".join([f"Example: {ex['riddle']} | {ex['answer']}" for ex in examples])
            prompt += f"\nHere are some examples:\n{example_text}"
    ```

### Grounding Technique 2: Prompt Engineering

**Prompt engineering** is the art of crafting a good prompt. A well-crafted prompt can dramatically improve the quality of the model's response.

*   **How it works:** When evaluating a user's answer, we give the model a specific persona ("You are an expert..."), provide it with context, and tell it exactly how to respond ("Respond ONLY with 'Correct' or 'Incorrect'").

*   **Code Snippet (`main.py`):**
    ```python
    prompt = (
        f"You are an expert in Kinyarwanda riddles (Ibisakuzo). The riddle's correct answer is '{target_text}'. "
        f"The user guessed '{user_answer}'. "
        f"Is the user's guess a correct or acceptable answer for this riddle? "
        f"Consider common variations and synonyms. Respond ONLY with 'Correct' or 'Incorrect'."
    )
    ```

### Multimodality: Transcribing Audio

Gemini is a **multimodal** model, which means it can understand different types of input, including text and audio. We use this feature in dev mode to transcribe audio.

*   **How it works:** The application sends the audio file directly to the Gemini API and asks it to transcribe the audio into text.

*   **Code Snippet (`main.py`):**
    ```python
    @app.post("/transcribe")
    async def transcribe_audio(audio_file: UploadFile = File(...)):
        if DEV_MODE:
            # Path A: Use Gemini for transcription
            logger.info("Transcribing audio using Gemini in Dev Mode...")
            audio_blob = {
                'mime_type': audio_file.content_type,
                'data': await audio_file.read()
            }
            response = await model.generate_content_async(["Transcribe this Kinyarwanda audio:", audio_blob])
            return TranscribeResponse(transcript=response.text)
        else:
            # Path B: Use the dedicated Google Cloud Speech-to-Text API
            # ...
    ```

-----

## 5. Troubleshooting Common Issues

*   **`ModuleNotFoundError: No module named 'google.generativeai'`**
    *   **Solution:** You forgot to install the dependencies! Run `pip install -r requirements.txt`.

*   **`503 Service Unavailable` for `/get_challenge`**
    *   **Solution:** This usually means your `GEMINI_API_KEY` is missing or invalid. Double-check your `.env` file.

*   **Audio buttons are disabled in Production Mode.**
    *   **Solution:** This means the dedicated audio APIs failed to initialize. Make sure you have run the `./setup_gcloud.sh` script and that billing is enabled on your Google Cloud project.

-----

Thank you for following this guide. We can't wait to see what you create. Happy coding!
