# Bavuga Ntibavuga - A Generative AI Language Game

## Overview

**Bavuga Ntibavuga** is an interactive and educational language game powered by Google's Gemini model. It's designed to be a fun way to learn Kinyarwanda through a variety of challenges, from translating proverbs to solving traditional riddles. The entire game experience, from challenge creation to answer evaluation, is driven by generative AI.

This project serves as a practical example for the "Google Cloud Skills Boost" session, demonstrating how to build dynamic, intelligent, and engaging applications with modern AI and MLOps principles.

## Key Features

*   **Multiple Game Modes:**
    *   **Story Mode:** An immersive narrative experience where challenges are part of an unfolding story.
    *   **BavugaNtiBavuga Mode:** Classic translation challenges with proverbs and common phrases.
    *   **Sakwe Sakwe Mode:** Traditional Kinyarwanda riddles (Ibisakuzo).
    *   **Image Mode:** Describe images of Rwanda in Kinyarwanda or English.
*   **AI-Powered:** All challenges and answer evaluations are handled by the Gemini model, creating a flexible and dynamic gameplay experience.
*   **Audio Input/Output:** (Production Mode) Use your voice to answer and hear the feedback spoken back to you.

## Getting Started

To run the application on your local machine and explore the code, please refer to the detailed instructions in our developer's guide:

**[>> Go to the Session Guide (sessionguide.md)](sessionguide.md)**

The session guide provides a complete walkthrough for setting up the project in both a simplified development mode and a full production environment with Docker.

## For Developers & Session Attendees

This repository is designed to be an educational resource. Here’s where to look to understand how it all works:

*   **Technical Deep Dive:** For a full explanation of the architecture, game modes, and how we use the Gemini API, please see the [sessionguide.md](sessionguide.md).
*   **MLOps Theory:** The `MLOps/` directory contains the Google Cloud whitepapers that form the theoretical foundation for the MLOps principles applied in this project.
*   **Core Application Logic:** The heart of the application can be found in `main.py`, which contains the FastAPI server and all the game logic.
*   **Database Logic:** The logic for interacting with the database (MongoDB in production, JSON file in dev mode) is in `db_logic.py`.

## A Note on AI Evaluation

A key feature of this application is that the Gemini model itself determines if an answer is correct. There isn't a hardcoded set of rules for the translations; the AI handles the linguistic evaluation, making the game more flexible and "human-like" in its understanding.
But keep in mind that its terrible at evaluating kinyarwanda maybe a a model with more data on Rwanda and Kinyarwanda can do evaluation of user responses much better than the gemini model.


---
