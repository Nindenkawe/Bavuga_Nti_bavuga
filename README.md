# Bavuga Ntibavuga - Language Learning Game

## Overview
Bavuga Ntibavuga (Kinyarwanda for "They speak, they don't speak") is an interactive language learning game designed to help users improve their Kinyarwanda and English translation skills. The game leverages Google's Gemini AI to generate dynamic challenges and evaluate user responses, providing an engaging and adaptive learning experience.

## Features
*   **AI-Powered Challenge Generation:** Challenges are dynamically created by an AI model, adapting to user performance and difficulty levels.
*   **Kinyarwanda-English Translation:** Practice translating proverbs and phrases between Kinyarwanda and English.
*   **Image Description Challenges:** Occasionally, users are presented with images to describe in either language, adding a visual dimension to learning.
*   **Intelligent Answer Evaluation:** AI evaluates user answers, considering synonyms and grammatical variations, not just exact matches.
*   **Scoring and Lives System:** Track your progress with a score and manage your lives, adding a gamified element.
*   **Containerized Setup:** Easily run the application using Docker Compose for a consistent development and testing environment.

## How It Works

### Challenge Generation
The application uses the Gemini AI model to generate diverse challenges. The AI acts as an expert in Kinyarwanda and English, creating proverbs, phrases, or image description tasks. It considers the user's previous incorrect answers to tailor future challenges, aiming for adaptive learning. Challenges are formatted for easy parsing by the application.

### Answer Evaluation
When a user submits an answer, the application sends both the user's answer and the correct target text to the Gemini AI. The AI, acting as a language expert, evaluates the submission for correctness, considering nuances like synonyms and minor grammatical differences. It returns a simple "Correct" or "Incorrect" verdict.

**Important Note on Correctness Logic:**
The determination of whether an answer is "correct" or "incorrect" is entirely handled by the integrated AI model. It performs a nuanced linguistic evaluation rather than a simple string comparison. This means the AI interprets the meaning and context of the user's input against the expected answer. The specific "context" and "text" logic for this determination resides within the AI's understanding and not explicitly coded as a set of rules within the application's Python files.

### Scoring and Game Logic
*   **Correct Answers:** Award points and maintain lives.
*   **Incorrect Answers:** Result in a loss of a life. The incorrect answer is noted to inform future AI challenge generation.
*   **Game Over:** If lives reach zero, the game resets, encouraging users to try again.

## Setup

### Prerequisites
*   Docker and Docker Compose installed on your system.
*   A Google API Key for the Gemini API. You can obtain one from [Google AI Studio](https://aistudio.google.com/app/apikey).

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Nindenkawe/Bavuga_Nti_bavuga.git
    cd Bavuga_Nti_bavuga
    ```

2.  **Configure Environment Variables:**
    Create a `.env` file in the root directory of the project by copying the example:
    ```bash
    cp .env.example .env
    ```
    Open the newly created `.env` file and replace `your_google_api_key_here` with your actual Google API Key:
    ```
    # Gemini API Key
    GOOGLE_API_KEY=your_google_api_key_here

    # MongoDB connection URI for Docker
    MONGODB_URI=mongodb://db:27017/

    # Name of the database
    DATABASE_NAME=language_app
    ```

3.  **Build and Run with Docker Compose:**
    ```bash
    docker-compose up --build
    ```
    This command will:
    *   Build the Docker image for the FastAPI application.
    *   Start the FastAPI application container.
    *   Start a MongoDB database container.
    *   Link the two services, allowing your application to connect to the database.

## How to Play
Once the Docker containers are running, open your web browser and navigate to `http://localhost:8000`.

*   You will be presented with a language challenge.
*   Enter your translation or description in the input field.
*   Click "Submit" to see if your answer is correct.
*   Your score and lives will update accordingly.
*   A new challenge will appear after a short delay.

## Technologies Used
*   **Backend:** FastAPI (Python)
*   **Frontend:** HTML, CSS (TailwindCSS for utility classes), JavaScript
*   **Database:** MongoDB (via Motor - async Python driver)
*   **AI:** Google Gemini API
*   **Containerization:** Docker, Docker Compose

## Contributing
Feel free to fork the repository, make improvements, and submit pull requests.

## License
[Consider adding a license here, e.g., MIT License]
