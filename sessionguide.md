# Bavuga Ntibavuga: Developer's Deep Dive Guide

Welcome, developer, to **Bavuga Ntibavuga**. This project is a practical showcase of modern Python web development, featuring a modular, AI-powered backend built with FastAPI and the `genai-processors` library.

This guide will walk you through the project's architecture, from the FastAPI entrypoint to the AI-powered processors, providing accurate code snippets and explanations to get you up to speed quickly.

**Tech Stack Overview:**
*   **Backend:** FastAPI
*   **AI/ML:** Google Gemini (via `google-generativeai`)
*   **Core Logic:** `genai-processors` library
*   **Database:** MongoDB (for production), JSON (for dev)
*   **Deployment:** Docker & Docker Compose
*   **API Specification:** Pydantic

---

## 1. High-Level Architecture: The `genai-processors` Flow

The application's logic is built around the `genai_processors.processor.Processor` class. Each logical unit (e.g., generating challenges, evaluating answers) is a `Processor`. These are chained together to perform complex tasks.

**The Core Data Flow:**

1.  An HTTP request arrives at an API route (e.g., in `api/http_routes.py`).
2.  The route handler constructs a JSON string containing instructions (e.g., `{"action": "get_challenge", ...}`).
3.  This JSON is wrapped in a `ProcessorPart` and put into a `stream`.
4.  This input stream is sent to the main `GameProcessor`.
5.  The `GameProcessor` routes the stream to a specialized sub-processor (like `ChallengeGeneratorProcessor`).
6.  The sub-processor executes its logic, often calling the Gemini API, and `yield`s its own output stream of `ProcessorPart`s.
7.  The original route handler consumes this output stream, decodes the JSON from the `ProcessorPart`, and returns a final HTTP response.

This stream-based, modular design makes the logic highly composable and testable.

---

## 2. Setup and Execution

*(This section is accurate and remains unchanged)*

### Path A: Gemini Dev Mode (Recommended for Quick Start)
*   **Goal:** Run the full application, including all audio features, with minimal setup.
*   **Setup:**
    1.  Create a `.env` file and add your `GEMINI_API_KEY`.
    2.  Install dependencies: `pip install -r requirements.txt`
    3.  Run the app: `./start.sh --dev`

### Path B: Full Production Mode
*   **Goal:** Deploy the complete, containerized application with a persistent database.
*   **Setup:**
    1.  Ensure Docker is installed.
    2.  Fill out your `.env` file completely.
    3.  Run the one-time cloud setup: `./setup_gcloud.sh YOUR_PROJECT_ID`
    4.  Launch: `docker-compose up --build -d`

---

## 3. Code Deep Dive

Let's explore the key components of the application.

### `main.py`: The Application Entrypoint

This file configures and launches the FastAPI application. Its most important function is the `lifespan` context manager, which initializes all the core processors and stores them in the `context` module, making them available to the rest of the app.

```python
# @/main.py - Processor Initialization

import context
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor
from processors.game_logic.game_processor import GameProcessor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... logging, DB connection, API key checks ...

    # --- Processor Initialization ---
    # Create instances of the core logic processors
    context.challenge_generator = ChallengeGeneratorProcessor(models)
    context.answer_evaluator = AnswerEvaluatorProcessor(models)
    
    # The GameProcessor holds the other two, acting as a router
    context.game_processor = GameProcessor(
        context.challenge_generator, 
        context.answer_evaluator
    )
    
    # ... audio processor initialization ...
            
    logger.info("All processors initialized.")
    yield # Application runs here
    
    # ... shutdown logic ...
```

### `api/models.py`: The Data Contracts

This file uses Pydantic to define the structure of API responses. This ensures that all data sent from the API is validated and conforms to a strict schema.

```python
# @/api/models.py - Pydantic Models

from pydantic import BaseModel

class ChallengeResponse(BaseModel):
    challenge_id: str
    source_text: str
    context: str | None = None
    challenge_type: str
    error_message: str | None = None

class SubmissionResponse(BaseModel):
    message: str
    is_correct: bool
    correct_answer: str | None = None
    score_awarded: int
    new_total_score: int
    lives: int
    score: int
```

### `api/http_routes.py`: The Primary Web Interface

This file defines the main RESTful endpoints. The `/get_challenge` endpoint is a perfect example of the core data flow.

```python
# @/api/http_routes.py - /get_challenge endpoint

from genai_processors import streams
from genai_processors.content_api import ProcessorPart
import context
from api.models import ChallengeResponse

@router.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(request: Request, ...):
    # 1. Construct the input data as a dictionary
    input_data = {
        "action": "get_challenge",
        "difficulty": difficulty,
        "state": json.loads(current_state.model_dump_json(by_alias=True)),
        "game_mode": game_mode,
    }
    input_json = json.dumps(input_data)

    # 2. Wrap the JSON in a ProcessorPart and create a stream
    input_stream = streams.stream_content([ProcessorPart(input_json)])

    # 3. Call the main game processor with the stream
    response_json = ""
    async for part in context.game_processor(input_stream):
        if part.text:
            response_json += part.text
    
    # 4. Decode the JSON response from the processor
    try:
        challenge_data = json.loads(response_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to decode response")

    # ... save challenge to DB and format the final HTTP response ...
    
    return ChallengeResponse(**challenge_data)
```

### `processors/game_logic/game_processor.py`: The Central Router

This processor is the entry point for all game logic requests from the HTTP routes. It's a simple but crucial router that inspects the `"action"` field in the input JSON and passes the stream to the correct sub-processor.

```python
# @/processors/game_logic/game_processor.py

from genai_processors import processor, streams
from genai_processors.content_api import ProcessorPart
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor

class GameProcessor(processor.Processor):
    def __init__(self, challenge_generator: ChallengeGeneratorProcessor, answer_evaluator: AnswerEvaluatorProcessor):
        self.challenge_generator = challenge_generator
        self.answer_evaluator = answer_evaluator

    async def call(self, input_stream: AsyncIterable[ProcessorPart]) -> AsyncIterable[ProcessorPart]:
        # ... (code to extract input_json from stream) ...
        
        input_data = json.loads(input_json)
        action = input_data.get("action")

        # Route based on the 'action' field
        if action == "get_challenge":
            chain_input_stream = streams.stream_content([ProcessorPart(input_json)])
            async for part in self.challenge_generator(chain_input_stream):
                yield part
        
        elif action == "evaluate_answer":
            chain_input_stream = streams.stream_content([ProcessorPart(input_json)])
            async for part in self.answer_evaluator(chain_input_stream):
                yield part
        # ...
```

### `processors/challenge_generator.py`: The Creative AI Director

This is where the core prompt engineering happens. For the "Sakwe Sakwe" riddles, it uses **Retrieval-Augmented Generation (RAG)** by loading examples from `riddles.json` to give the AI context.

```python
# @/processors/challenge_generator.py - RAG for Riddles

class ChallengeGeneratorProcessor(processor.Processor):
    def __init__(self, model_names: list[str], image_dir: str = "sampleimg"):
        # ...
        self.ibisakuzo_examples = self._load_riddles() # Loads riddles.json
        # ...

    async def _generate_challenge_logic(self, ...):
        # ...
        if game_mode == "sakwe":
            if not self.ibisakuzo_examples: 
                return {"error_message": "Riddle database is empty."}
            
            # This is a simplified RAG. It currently picks a random riddle from the loaded JSON file.
            riddle_data = random.choice(self.ibisakuzo_examples)
            
            # The response initiates the multi-step riddle game on the frontend
            return {
                "challenge_type": "gusakuza_init", 
                "source_text": "Sakwe sakwe!", 
                "target_text": f"{riddle_data['riddle']}|{riddle_data['answer']}", 
                "context": "Reply with 'soma' to get the riddle."
            }
        # ...
```

### `processors/answer_evaluator.py`: The AI Grader

This processor evaluates the user's answer. It uses a simple string comparison for riddles (which must be exact) and a call to the Gemini API for translation challenges.

```python
# @/processors/answer_evaluator.py

class AnswerEvaluatorProcessor(processor.Processor):
    def __init__(self, model_names: list[str]):
        # ...
        self.prompt = (
            "You are an expert in Kinyarwanda and English. "
            "The target text is '{target_text}'. The user's answer is '{user_answer}'. "
            "Is the user's answer a correct translation? "
            "Consider synonyms and minor grammatical variations. "
            "Respond ONLY with 'Correct' or 'Incorrect'."
        )
        # ...

    async def call(self, input_stream: AsyncIterable[ProcessorPart]) -> AsyncIterable[ProcessorPart]:
        # ... (code to extract input_data from stream) ...
        
        challenge_type = input_data["challenge_type"]

        # For riddles, the answer must be culturally exact. No AI needed.
        if challenge_type == "gusakuza":
            is_correct = user_answer.lower().strip() == target_text.lower().strip()
            yield ProcessorPart(json.dumps({"is_correct": is_correct}))
            return

        # For other types, format the prompt and call the Gemini model
        formatted_prompt = self.prompt.format(...)
        # ... (call GenaiModel and yield the result) ...
```

### Audio and Real-time WebSockets

The project has two distinct modes of audio handling:

1.  **RESTful Audio (`http_routes.py`):** The `/transcribe` and `/synthesize` endpoints handle audio as discrete uploads and downloads. This is the primary, functioning implementation for general purpose STT/TTS.
2.  **Streaming Audio (`websocket_routes.py`):** The `/ws/sakwe` endpoint is a more advanced, proof-of-concept implementation for a fully interactive, real-time riddle game. It uses a dedicated `SakweProcessor` to manage a streaming conversation.

**NOTE:** The `processors/audio.py` file currently contains **placeholder/simulator functions** for Gemini STT/TTS. The actual audio processing is handled directly within the API routes for now. This indicates that a unified audio processor is a future development goal.

---

## 4. Game Mode Deep Dive: Prompts and Logic

This section details the specific logic, AI prompting, and response handling for each game mode, all of which are orchestrated by the `ChallengeGeneratorProcessor`.

When the `--debug` flag is enabled, the application log becomes highly verbose. The most useful output for understanding the AI interaction comes from the `ChallengeGeneratorProcessor`’s `_run_processor` method, which logs the exact prompt sent to the Gemini API and the raw response received from it.

---

### Translation Mode

*   **Goal:** Provide a classic translation challenge, either a common phrase or a proverb.
*   **How it Works:** This is the most direct use of the Gemini API. The processor randomly chooses to either generate a Kinyarwanda proverb to translate to English or a simple English phrase to translate to Kinyarwanda.

*   **Prompt Engineering:** A simple, direct instruction is sent to the model.

    ```python
    # @/processors/challenge_generator.py - Translation Prompts
    
    # When generating an English phrase to translate
    prompt = "Provide a simple {level} English phrase and its Kinyarwanda translation, separated by a pipe (|). Example: 'Good morning|Mwaramutse'. No other text."
    
    # When generating a Kinyarwanda proverb
    prompt = "Provide a {level} Kinyarwanda proverb and its English translation, separated by a pipe (|). Example: 'Akabando k'iminsi gacibwa kare|A walking stick for old age is prepared in advance'. No other text."
    ```

*   **Response Handling:** The processor expects a simple string response containing the two phrases separated by a pipe (`|`). It splits this string to get the `source_text` and `target_text`.

    ```
    # AI Response Example:
    "I'm hungry|Ndashonje"
    
    # Parsed by the processor into:
    source_text = "I'm hungry"
    target_text = "Ndashonje"
    ```

---

### Image Mode

*   **Goal:** Test the user's descriptive skills by asking them to describe an image in either Kinyarwanda or English.
*   **How it Works:** This mode showcases Gemini’s **multimodal** capabilities. The processor selects a random image from the `/sampleimg` directory and sends it to the model along with a text prompt.

*   **Prompt Engineering:** The input sent to the `genai-processor` is a list containing multiple `ProcessorPart` objects: one for the text instructions and one for the image data.

    ```python
    # @/processors/challenge_generator.py - Image Mode Logic
    
    # 1. The text prompt
    prompt = "Describe this image of Rwanda in a single, descriptive sentence. Provide the description in both Kinyarwanda and English, separated by a pipe (|). Example: 'Umusozi w'u Rwanda|A Rwandan hill'. No other text."
    
    # 2. The image is opened with PIL
    from PIL import Image
    img = Image.open("sampleimg/Rw1.jpg")

    # 3. Both are sent to the model
    # (Conceptual code, the processor handles the stream wrapping)
    # model.generate_content([prompt, img]) 
    ```

*   **Response Handling:** The processor expects a single text string with the two descriptions, separated by a pipe. The `source_text` of the challenge is set to the image URL for the frontend to display.

    ```
    # AI Response Example:
    "Icyayi gihinze ku misozi|Tea planted on the hills"

    # Parsed by the processor into:
    source_text = "/sampleimg/Rw1.jpg"
    target_text = "Kinyarwanda: Icyayi gihinze ku misozi | English: Tea planted on the hills"
    ```

---

### Story Mode

*   **Goal:** Create an immersive, narrative-driven experience where challenges are derived from an unfolding story.
*   **How it Works:** This is a stateful, multi-step process that uses the AI for both world-building and challenge creation.

    1.  **Story Generation:** If the user’s session has no story, the processor first makes a call to the Gemini API with a prompt asking it to create a 3-chapter story about Rwanda, formatted as JSON. This JSON is saved in the user’s session.
    2.  **Challenge Generation:** The processor then takes the current chapter from the saved story and uses it as context in a *second* prompt, asking the AI to create a specific translation challenge based on that chapter.

*   **Prompt Engineering:** Two distinct prompts are used.

    ```python
    # @/processors/challenge_generator.py - Story Mode Prompts

    # Prompt 1: To create the story
    story_creation_prompt = "Write a short, engaging story for a language learning game about exploring Rwanda. Break the story into 3 chapters... Output a JSON object with a 'title' and a list of 'chapters'..."

    # Prompt 2: To create a challenge from a chapter
    story_translation_prompt = "Based on this story chapter: '{story_chapter_text}', create a language challenge. It should be a phrase from the story to translate from English to Kinyarwanda. Output as 'English phrase|Kinyarwanda translation'."
    ```

*   **Response Handling:** The processor must first be able to parse the JSON response for story creation, then the standard `source|target` format for the challenge itself.

---

### Sakwe Sakwe (Riddle) Mode

*   **Goal:** Recreate the traditional Rwandan "Sakwe Sakwe" riddle game.
*   **How it Works:** This mode is unique as it **does not use the AI to generate the challenge**. Instead, it uses pure **Retrieval** from a curated list to ensure cultural authenticity. The flow is controlled by the frontend and multiple backend endpoints.

    1.  **Initiation (`/get_challenge`):** The `ChallengeGeneratorProcessor` picks a random riddle and its answer from the `riddles.json` file. It returns a special `gusakuza_init` challenge.
    2.  **User Interaction (Frontend):** The frontend displays "Sakwe sakwe!" and the user must respond by clicking a "Soma" button.
    3.  **Revelation (`/soma`):** The click calls the `/soma` endpoint. The backend retrieves the pending riddle from the user’s session and returns it as a proper challenge for the user to answer.

*   **Prompt Engineering:** No AI prompt is used to generate the riddle. The "prompt" is the act of reading from the local `riddles.json` file.

*   **Response Handling:** The initial response is a special object that the frontend knows how to handle to display the "Soma" button.

    ```json
    // Response from /get_challenge for sakwe mode
    {
      "challenge_type": "gusakuza_init",
      "source_text": "Sakwe sakwe!",
      "target_text": "Nyirabiyoro arabyina mu iroza|Ikinyugunyugu", // The hidden riddle|answer
      "context": "Reply with 'soma' to get the riddle.",
      "challenge_id": "gusakuza_init"
    }
    ```
*   **Answer Evaluation:** As seen in the `AnswerEvaluatorProcessor`, answers to riddles are checked for an exact match, bypassing the AI to respect the precise nature of traditional answers.

---
This guide should provide a solid foundation for understanding the Bavuga Ntibavuga application. Happy coding!
