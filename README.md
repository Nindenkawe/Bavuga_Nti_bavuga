# Bavuga Ntibavuga - AI Word Game

## Overview
Bavuga Ntibavuga is a simple word game where you play against a generative AI. The AI creates language challenges, and you provide the answers. It's designed to be a fun and interactive way to engage with AI in a word game context.

## How It Works
*   **AI-Generated Challenges:** The game uses a generative AI model to create various word-based challenges.
*   **AI Evaluates Answers:** The same AI model also determines if your answers are correct, providing a dynamic and flexible evaluation.
*   **Simple Gameplay:** Just answer the challenges presented by the AI and see how well you do!

## Setup
To run this project, you will need Docker and a Google API Key for the Gemini API. Follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Nindenkawe/Bavuga_Nti_bavuga.git
    cd Bavuga_Nti_bavuga
    ```
2.  **Configure your API Key:**
    Copy `.env.example` to `.env` and replace `your_google_api_key_here` with your actual Google API Key.
    ```bash
    cp .env.example .env
    ```
3.  **Run with Docker Compose:**
    ```bash
    docker-compose up --build
    ```
    Then, open your browser to `http://localhost:8000`.

## Note on Correctness Logic
The AI model itself determines if an answer is correct. There isn't a separate, explicit set of rules coded in the application for this; the AI handles the linguistic evaluation.