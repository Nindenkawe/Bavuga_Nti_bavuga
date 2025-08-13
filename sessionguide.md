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
    chmod +x start.sh

    # Engage Gemini Dev Mode!
    ./start.sh --dev

    # To see the Gemini API requests and responses in real-time, use the --debug flag:
    ./start.sh --dev --debug
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

## 4. Understanding the Magic: How Gemini Powers Each Game Mode

This application is more than just a game; it's a practical demonstration of how to creatively interact with a powerful Large Language Model (LLM) like Gemini. By sending the model different types of data and instructions (a process called **grounding**), we can shape its output to create diverse and engaging experiences.

Let's explore how each game mode uses Gemini in a unique way.

---

### **Story Mode: The Narrator**

*   **The Goal:** Create an immersive, narrative-driven experience where each challenge is part of an unfolding story.
*   **The Logic:** This mode showcases Gemini's ability to generate structured, creative content.
    1.  **Story Generation:** If no story exists, we ask Gemini to become a storyteller. We send a detailed prompt asking for a short story, broken into chapters, and formatted as a JSON object.
    2.  **Challenge Generation:** For each challenge, we provide Gemini with the current chapter of the story and ask it to create a translation challenge based on the chapter's content.
*   **Data Structures:**
    *   **Input for Story:** A detailed text prompt describing the desired story structure and format (JSON).
    *   **Output for Story:** A JSON object containing the story's title and a list of chapters.
    *   **Input for Challenge:** A text prompt that includes a chapter of the story as context.
*   **Code Snippet (`main.py`):**
    ```python
    # Story Generation Prompt
    story_prompt = "Write a short, engaging story for a language learning game... The output should be a JSON object with a 'title' and a list of 'chapters'..."
    
    # Challenge Generation Prompt
    prompt = f"Based on this chapter of a story: '{chapter_text}', create a language challenge... in the format 'English phrase|Kinyarwanda translation'."
    ```

---

### **BavugaNtiBavuga Mode: The Translator**

*   **The Goal:** Generate classic translation challenges, like translating proverbs or common phrases.
*   **The Logic:** This is the most direct use of Gemini's translation capabilities. We provide a simple instruction and let the model do the work.
*   **Data Structures:**
    *   **Input:** A simple text prompt asking for a phrase and its translation, separated by a pipe (`|`).
    *   **Output:** A single string containing the two translated phrases.
*   **Code Snippet (`main.py`):**
    ```python
    prompt = f"Provide a simple {level} English phrase and its Kinyarwanda translation, separated by a pipe (|). Example: 'Good morning|Mwaramutse'."
    ```

---

### **Sakwe Sakwe Mode: The Cultural Expert**

*   **The Goal:** Create challenges based on traditional Kinyarwanda riddles (Ibisakuzo).
*   **The Logic:** This mode demonstrates a powerful technique called **Retrieval-Augmented Generation (RAG)**. We don't just ask Gemini to generate a riddle; we give it examples from our `riddles.json` file to ensure the riddles are authentic and culturally relevant. This is also known as **few-shot prompting**.
*   **Data Structures:**
    *   **Input:** A text prompt that includes several examples of real riddles and their answers.
    *   **Output:** A new riddle and answer that mimics the style and structure of the examples.
*   **Code Snippet (`main.py`):**
    ```python
    # The prompt is augmented with examples from the riddles.json file
    prompt = "Generate a Kinyarwanda riddle (igisakuzo)... Here are some examples:
" + example_text
    ```

---

### **Image Mode: The Artist & Interpreter**

*   **The Goal:** Create challenges based on describing an image.
*   **The Logic:** This mode uses Gemini's **multimodal** capabilities, meaning it can understand both text and images.
    1.  We send the model an image file from our local directory.
    2.  We also send a text prompt asking the model to describe the image in both Kinyarwanda and English.
*   **Data Structures:**
    *   **Input:** A list containing both a text prompt and an image file. This is a key concept in multimodality.
    *   **Output:** A text string with the Kinyarwanda and English descriptions.
*   **Code Snippet (`main.py`):**
    ```python
    prompt = [
        "Describe this image of Rwanda in a single, descriptive sentence...",
        img, # The PIL Image object
    ]
    ```

---

### **Multimodality in Dev Mode: The Transcriber**

In the Gemini Dev Mode, we also use multimodality for audio transcription.

*   **How it works:** The application sends the recorded audio file directly to the Gemini API and asks it to transcribe the audio into text.
*   **Data Structures:**
    *   **Input:** A list containing a text prompt ("Transcribe this Kinyarwanda audio:") and the audio data.
*   **Code Snippet (`main.py`):**
    ```python
    response = await model.generate_content_async(["Transcribe this Kinyarwanda audio:", audio_blob])
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