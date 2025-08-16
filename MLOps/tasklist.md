# Project Status & Next Steps

This document provides a clear overview of the completed tasks, remaining work, and suggestions for testing the "Bavuga Ntibavuga" application.

---

## Completed Tasks

### 1. Foundational Refactoring to `genai-processors`
-   **Core Logic:** The application's core logic was refactored into modular, maintainable, and chainable processors (`ChallengeGeneratorProcessor`, `AnswerEvaluatorProcessor`, `GameProcessor`).
-   **Integration:** FastAPI endpoints and the main application lifecycle now use the new processor-based architecture.
-   **Cleanup:** Old, monolithic game logic functions have been removed.

### 2. "Gusakuza" Riddle Game
-   **Authentic Riddles:** The game uses Retrieval-Augmented Generation (RAG), pulling real riddles from a curated `riddles.json` file to ensure cultural authenticity.
-   **Full Game Flow:** The multi-step "sakwe sakwe" -> "soma" -> riddle flow is fully implemented on both the frontend and backend.
-   **AI-Powered Hints:** The AI is used to generate helpful hints for the riddles.

### 3. Live Audio Transcription Feature
-   **Real-time Streaming:** The application now supports live audio streaming from the client to the server using WebSockets.
-   **Dual-Mode Processing:**
    -   **Production:** Uses Google Cloud Speech-to-Text for live, accurate transcriptions.
    -   **Development:** Uses a `MockStreamingAudioProcessor` to simulate transcription, allowing for easy local development without cloud credentials.
-   **UI Integration:** The frontend features a microphone button for recording, and the transcribed text is automatically placed in the answer input field.

### 4. Documentation
-   **Developer Guide:** The `sessionguide.md` has been thoroughly updated to reflect the new architecture, including detailed explanations of the live audio feature and the AI techniques used.

---

## Remaining Tasks

-   [ ] **Persist Game State to Database**
    -   **Goal:** Currently, the game state (score, lives, etc.) is stored in-memory and is lost on page refresh. This task involves modifying the application to save and retrieve game state from MongoDB when in production mode.
    -   **Files to Update:** `db_logic.py`, `api/http_routes.py`.

-   [ ] **Comprehensive End-to-End Testing**
    -   **Goal:** Now that the core features are in place, a thorough round of end-to-end testing is needed to ensure all parts of the application work together seamlessly.

---

## Suggestions for Further Testing

This section outlines specific areas to test to understand the behavior and limits of the AI models.

### 1. Answer Evaluation (`AnswerEvaluatorProcessor`)
-   **Synonyms & Paraphrasing:** How well does the AI handle answers that are correct in meaning but not an exact word-for-word match? (e.g., "The sky is blue" vs. "The heavens are azure").
-   **Minor Errors:** Does the AI correctly identify answers with small typos or grammatical mistakes?
-   **Language Mismatch:** What happens if a user answers in the wrong language (e.g., English for a Kinyarwanda prompt)?

### 2. Challenge Generation (`ChallengeGeneratorProcessor`)
-   **Difficulty Levels:** Is there a noticeable and consistent difference in the difficulty of challenges when you select beginner, intermediate, or advanced?
-   **Story Variety:** In "Story Mode," how diverse are the generated stories? Do they become repetitive after several new games?
-   **Image Generation:** In "Image Mode," assess the quality and variety of the AI-generated images and their corresponding descriptions.

### 3. Live Transcription (Google Cloud Speech-to-Text)
-   **Accents & Pacing:** How does the transcription quality vary with different accents, dialects, and speaking speeds?
-   **Background Noise:** Test the transcription accuracy in a noisy environment.
-   **Ambiguous Words:** How well does the model handle homophones or words that sound similar?

### 4. Riddle Hints
-   **Hint Quality:** For the "Sakwe Sakwe" riddles, are the AI-generated hints helpful? Are they too easy, too cryptic, or just right?
