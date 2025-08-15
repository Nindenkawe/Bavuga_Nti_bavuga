# Project Improvement Task List

This file outlines the tasks to improve the "Bavuga Ntibavuga" web application. It tracks what has been completed and what is still pending.

## Foundational Refactoring to Processors

This was a major refactoring to make the codebase modular, maintainable, and ready for real-time features. 

-   [x] **Phase 1: Setup and Core Structure**
    -   **Status:** Done.
    -   [x] **Task 1.1:** Add `google-deepmind-genai-processors` to `requirements.txt`.
    -   [x] **Task 1.2:** Create the `processors` directory and initialize it as a Python package.

-   [x] **Phase 2: Refactoring Core Logic into Processors**
    -   **Status:** Done.
    -   [x] **Task 2.1:** Created `processors/challenge_generator.py` and refactored all challenge generation logic into a `ChallengeGeneratorProcessor` class.
    -   [x] **Task 2.2:** Created `processors/answer_evaluator.py` and refactored answer evaluation logic into an `AnswerEvaluatorProcessor` class.
    -   [x] **Task 2.3:** Created `processors/game_logic/game_processor.py` to orchestrate the game flow using the other processors.

-   [x] **Phase 3: Integration and Cleanup**
    -   **Status:** Done.
    -   [x] **Task 3.1:** In `main.py`, the application now initializes all the new processor classes within the FastAPI lifespan event.
    -   [x] **Task 3.2:** FastAPI endpoints (`/get_challenge`, `/submit_answer`, and WebSockets) were updated to use the new processors.
    -   [x] **Task 3.3:** All old game logic functions were removed from `main.py`.

-   [x] **Phase 4: Preparing for Audio Features**
    -   **Status:** Done.
    -   [x] **Task 4.1:** Created `processors/audio.py` with fully functional `GeminiTextToSpeechProcessor` and `GeminiSpeechToTextProcessor` classes, not just placeholders.

## Feature 1: "Gusakuza" Riddle Game

The "Gusakuza" traditional Rwandan riddle game was implemented as a new game mode.

-   **Status:** Done.
-   [x] **Task 1.1: Backend - AI Prompt for Riddles:**
    -   **Done:** The `ChallengeGeneratorProcessor` now uses Retrieval-Augmented Generation (RAG) by reading from `riddles.json` to create authentic riddles.
-   [x] **Task 1.2: Backend - New Game Mode Logic:**
    -   **Done:** The `gusakuza` challenge type is fully implemented within the `ChallengeGeneratorProcessor`.
-   [x] **Task 1.3: Frontend - UI for "Gusakuza" Game:**
    -   **Done:** The frontend successfully handles the multi-step "sakwe sakwe" -> "soma" -> riddle flow.
-   [x] **Task 1.4: Backend - Evaluate Riddle Answer:**
    -   **Done:** The `AnswerEvaluatorProcessor` correctly evaluates user answers for the riddles.

## Feature 2: Live Audio Chat

This feature allows the user to interact with the AI using their voice for a fully multimodal experience.

-   **Status:** Done.
-   [x] **Task 2.1: Frontend - Audio Recording:**
    -   **Done:** The UI has a microphone button that uses the MediaRecorder API to capture and stream audio to the backend via WebSockets.
-   [x] **Task 2.2: Backend - Speech-to-Text:**
    -   **Done:** A WebSocket endpoint receives the audio data and uses the `GeminiSpeechToTextProcessor` to get a live transcription.
-   [x] **Task 2.3: Backend - Text-to-Speech:**
    -   **Done:** The `GeminiTextToSpeechProcessor` is used to convert the AI's text responses into audio.
-   [x] **Task 2.4: Frontend - Audio Playback:**
    -   **Done:** The frontend receives the AI-generated audio and plays it back to the user.

## General Improvements & Next Steps

-   [ ] **Task 3.1: Refactor Game State to Database**
    -   **Status:** Not Done.
    -   **Goal:** Currently, game state (score, lives) is stored in-memory and is lost on refresh. This should be moved to the MongoDB database (for production mode) to persist state across sessions.
-   [ ] **Task 3.2: Code Cleanup and Refactoring**
    -   **Status:** Partially Done.
    -   **Notes:** The processor refactoring was a major cleanup. However, ongoing reviews of the frontend JavaScript and backend routing could lead to further improvements.
