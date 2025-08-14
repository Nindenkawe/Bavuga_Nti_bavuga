# Project Improvement Task List

This file outlines the tasks to improve the "Bavuga Ntibavuga" web application by making it more interactive.

## Refactoring to GenAI Processors

This is a foundational refactoring to make the codebase more modular, maintainable, and ready for real-time audio features. This should be completed before starting on Feature 2.

-   [ ] **Phase 1: Setup and Core Structure**
    -   [ ] **Task 1.1:** Add `google-deepmind-genai-processors` to `requirements.txt` and install it.
    -   [ ] **Task 1.2:** Create a new directory named `processors` and initialize it as a Python package.

-   [ ] **Phase 2: Refactoring Core Logic into Processors**
    -   [ ] **Task 2.1:** Create `processors/challenge_generator.py` and refactor `generate_challenge` logic into a `ChallengeGeneratorProcessor` class.
    -   [ ] **Task 2.2:** Create `processors/answer_evaluator.py` and refactor `evaluate_answer` logic into an `AnswerEvaluatorProcessor` class.

-   [ ] **Phase 3: Integration and Cleanup**
    -   [ ] **Task 3.1:** In `main.py`, import and initialize the new processor classes.
    -   [ ] **Task 3.2:** Update FastAPI endpoints (`/get_challenge`, `/submit_answer`) to use the new processors.
    -   [ ] **Task 3.3:** Remove the old `generate_challenge*` and `evaluate_answer*` functions from `main.py`.

-   [ ] **Phase 4: Preparing for Audio Features**
    -   [ ] **Task 4.1:** Create `processors/audio.py` with placeholder classes for `TextToSpeechProcessor` and `SpeechToTextProcessor`.

## Feature 1: "Gusakuza" Riddle Game

The "Gusakuza" game is a traditional Rwandan riddle game. The goal is to implement this as a new game mode.

-   [ ] **Task 1.1: Backend - AI Prompt for Riddles:**
    -   [ ] Create a new prompt for the AI agent to generate "Ibisakuzo" (riddles) in Kinyarwanda.
    -   [ ] The AI should provide the riddle and the correct answer.

-   [ ] **Task 1.2: Backend - New Game Mode Logic:**
    -   [ ] Add a new challenge type, `gusakuza`, in the `generate_challenge` function.
    -   [ ] Implement the "sakwe sakwe" -> "soma" interaction flow. This might require a new endpoint or state management to handle the multi-step nature of the game.

-   [ ] **Task 1.3: Frontend - UI for "Gusakuza" Game:**
    -   [ ] Create a new UI section or modify the existing one to handle the "Gusakuza" game.
    -   [ ] Display the "sakwe sakwe" prompt from the AI.
    -   [ ] Add a button or input for the user to respond with "soma".
    -   [ ] Display the riddle from the AI.
    -   [ ] Allow the user to input their answer to the riddle.

-   [ ] **Task 1.4: Backend - Evaluate Riddle Answer:**
    -   [ ] Use the AI to evaluate the user's answer to the riddle.
    -   [ ] Update the score and lives based on the result.

## Feature 2: Live Audio Chat

This feature will allow the user to interact with the AI using their voice.

-   [ ] **Task 2.1: Frontend - Audio Recording:**
    -   [ ] Add a microphone button to the UI.
    -   [ ] Use the MediaRecorder API to capture audio from the user's microphone.
    -   [ ] Send the audio data to the backend.

-   [ ] **Task 2.2: Backend - Speech-to-Text:**
    -   [ ] Create a new endpoint to receive audio data.
    -   [ ] Use a speech-to-text service (e.g., Google's Speech-to-Text API) to transcribe the user's audio.

-   [ ] **Task 2.3: Backend - Text-to-Speech:**
    -   [ ] Use a text-to-speech service (e.g., Google's Text-to-Speech API) to convert the AI's text response into audio.
    -   [ ] Send the audio data back to the frontend.

-   [ ] **Task 2.4: Frontend - Audio Playback:**
    -   [ ] Receive the audio response from the backend.
    -   [ ] Play the audio to the user.

## General Improvements

-   [ ] **Task 3.1: Refactor Game State:**
    -   [ ] Move the `game_state` dictionary from in-memory to the database to persist scores and lives across sessions. This would be more robust.
-   [ ] **Task 3.2: Code Cleanup and Refactoring:**
    -   [ ] Review and refactor the code for clarity and maintainability.