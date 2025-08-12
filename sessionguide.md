# Building a Local-First Generative AI App

Welcome everyone! Today, we're going to build and run a fun, educational Kinyarwanda language game called "Bavuga Ntibavuga," powered by Google's Generative AI. We'll focus on a local-first development workflow, using Docker Compose to run our entire application stack with a single command.

This guide will walk you through the key features, the technology behind them, and how to get everything running on your local machine.

-----

## 1. The Core Idea

"Bavuga Ntibavuga" is a language learning game that leverages generative AI to create dynamic challenges. Instead of static questions, our app uses the Gemini API to generate riddles ("Gusakuza"), proverbs, and translation tasks in real-time. It also features live audio interaction, allowing users to speak their answers and hear the AI's responses.

-----

## 2. Our Tech Stack

*   **Backend:** FastAPI (Python)
*   **Database:** MongoDB
*   **AI Models:**
    *   **Core Logic:** Google Gemini API via the `google-generativeai` library.
    *   **Speech-to-Text:** Google Cloud Speech-to-Text API via `google-cloud-speech`.
    *   **Text-to-Speech:** Google Cloud Text-to-Speech API via `google-cloud-texttospeech`.
*   **Containerization:** Docker Compose
*   **Frontend:** Vanilla HTML, TailwindCSS, and JavaScript.

-----

## 3. Getting Started: Authentication is Key

Our application interacts with multiple Google Cloud services, which require proper authentication.

*   **Gemini API:** Uses an API Key.
*   **Speech & Text-to-Speech APIs:** Use Application Default Credentials (ADC) via a service account JSON file.

To simplify this setup, we've created a script to automate the process.

### Automated Setup

Before running the application, execute the setup script from your terminal. You will need to provide your Google Cloud Project ID as an argument.

```bash
# Make the script executable
chmod +x setup_gcloud.sh

# Run the script with your Project ID
./setup_gcloud.sh YOUR_PROJECT_ID
```

This script will enable the necessary APIs, create a service account with the correct permissions, and generate a `google-credentials.json` file in your project directory. This file is automatically ignored by Git to keep your credentials secure.

-----

## 4. Dissecting the Code: The AI-Powered Backend

Let's dive into the most important parts of our `main.py` file.

### a) The AI Model

Instead of a high-level agent library, we interact directly with the `google-generativeai` library for more control. We initialize a model that will be used for generating challenges and evaluating answers.

**`main.py` Snippet:**
```python
# --- Generative AI Configuration ---
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is required.")
genai.configure(api_key=api_key)

# --- AI Model Configuration ---
model = genai.GenerativeModel(GEMMA_MODEL_NAME)
```
**Explanation:** We first configure our API key and then instantiate the `GenerativeModel`. This `model` object is our primary interface to the Gemini API for all text-based generation tasks.

### b) Generating a Challenge: The "Gusakuza" Flow

The `generate_challenge` function now has more complex logic to handle the two-step "Gusakuza" (riddle) game.

**`main.py` Snippet:**
```python
async def generate_challenge(difficulty: int, state: GameState) -> dict:
    # ... (code for selecting challenge type)
    challenge_type = random.choice(challenge_types)

    if challenge_type == "gusakuza":
        prompt = "Generate a Kinyarwanda riddle (igisakuzo). The response should be in the format 'riddle|answer'."
        response = await model.generate_content_async(prompt)
        # This is the initial "Sakwe sakwe!" part.
        return {
            "challenge_type": "gusakuza_init",
            "source_text": "Sakwe sakwe!",
            "target_text": response.text, # Store "riddle|answer"
            "context": "Reply with 'soma' to get the riddle.",
        }
    # ... (rest of the logic)
```
**Explanation:** When a `gusakuza` challenge is chosen, the app first generates the riddle and its answer from the AI. However, it stores the answer internally and sends a special `gusakuza_init` challenge to the frontend. The user first sees "Sakwe sakwe!" and must respond with "soma" (handled by a separate `/soma` endpoint) to receive the actual riddle.

### c) Evaluating the Answer

The `evaluate_answer` function uses Gemini to act as an expert judge, determining if the user's response is accurate.

**`main.py` Snippet:**
```python
async def evaluate_answer(user_answer: str, target_text: str, challenge_type: str) -> bool:
    # ... (prompt construction logic)
    prompt = (
        f"You are an expert in Kinyarwanda riddles (Ibisakuzo). The riddle's correct answer is '{target_text}'. "
        f"The user guessed '{user_answer}'. "
        # ...
        f"Respond ONLY with 'Correct' or 'Incorrect'."
    )
    response = await model.generate_content_async(prompt)
    return "correct" in response.text.lower()
```
**Explanation:** The prompt here is very specific, instructing the AI to respond *only* with "Correct" or "Incorrect." This allows us to use a simple string check to get a reliable boolean result.

### d) The Live Audio Chat Feature

We've added two new endpoints to handle voice interaction.

**`main.py` Snippet:**
```python
# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

@app.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    # ... (code to read audio file)
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="rw-RW",
    )
    response = speech_client.recognize(config=config, audio=audio)
    # ... (return transcript)

@app.post("/synthesize")
async def synthesize_speech(text: str = Form(...)):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="rw-RW", name="rw-RW-Standard-A"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    return StreamingResponse(io.BytesIO(response.audio_content), media_type="audio/mpeg")
```
**Explanation:** The `/transcribe` endpoint takes a recorded audio file and uses the Speech-to-Text API to convert it into Kinyarwanda text. The `/synthesize` endpoint does the reverse, converting a string of text into natural-sounding Kinyarwanda speech, which is then streamed back to the user.

-----

## 5. Running the Application with Docker Compose

Docker Compose allows us to run our entire application stack—the FastAPI backend and the MongoDB database—with a single command.

**`docker-compose.yml` Snippet:**
```yaml
name: bavuga-app

services:
  app:
    build: .
    image: bavuga-app:latest
    container_name: bavuga-app
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json
      - MONGODB_URI=mongodb://database:27017
      - DATABASE_NAME=language_app
    volumes:
      - ./google-credentials.json:/app/google-credentials.json:ro
    depends_on:
      database:
        condition: service_healthy

  database:
    image: mongo:latest
    # ... (rest of the database configuration)
```
**Explanation:**
*   The `app` service now includes a `GOOGLE_APPLICATION_CREDENTIALS` environment variable, which tells the Google Cloud libraries where to find the authentication file.
*   The `volumes` section mounts our local `google-credentials.json` file into the container in read-only (`:ro`) mode for security.

To run everything, first complete the authentication setup, then use the command:
```bash
docker-compose up --build -d
```
Your application will be available at `http://localhost:8000`.
