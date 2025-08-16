# Bavuga Ntibavuga: Developer's Deep Dive Guide

Welcome, developer, to **Bavuga Ntibavuga**. This project is a practical showcase of modern Python web development, featuring a modular, AI-powered backend built with FastAPI and the `genai-processors` library.

This guide will walk you through the project's architecture, from the FastAPI entrypoint to the AI-powered processors that form the core of the application. We will focus on how the `genai-processors` library simplifies our interaction with the Gemini model and how we leverage powerful AI techniques like prompt engineering, grounding, few-shot prompting, and Retrieval-Augmented Generation (RAG) to create a dynamic and culturally rich language learning experience.

**Tech Stack Overview:**
*   **Backend:** FastAPI
*   **AI/ML:** Google Gemini (via `google-generativeai`)
*   **Core Logic:** `genai-processors` library
*   **Database:** MongoDB (for production), JSON (for dev)
*   **Deployment:** Docker & Docker Compose
*   **API Specification:** Pydantic

---

## 1. The `genai-processors` Library: Our AI Abstraction Layer

The application's logic is built around the `genai_processors.processor.Processor` class. Instead of making direct, scattered calls to the Gemini API, we encapsulate all AI interactions within these processors. This design choice, facilitated by the `genai-processors` library, is central to our architecture.

**Why use this library?**

1.  **Simplicity:** It abstracts away the boilerplate of handling API keys, creating model clients, and processing request/response cycles. We can focus on the *logic* of our prompts, not the plumbing.
2.  **Modularity:** Each processor is a self-contained unit of logic (e.g., `ChallengeGeneratorProcessor`, `AnswerEvaluatorProcessor`). This makes the code easier to understand, maintain, and test.
3.  **Chainability:** The library is built on a foundation of asynchronous streams (`AsyncIterable[ProcessorPart]`). This allows us to chain processors together, passing the output of one as the input to another, creating complex AI workflows from simple, reusable blocks.

**The Core Data Flow:**

1.  An HTTP request arrives at an API route (e.g., in `api/http_routes.py`).
2.  The route handler wraps the request data into a `ProcessorPart` and puts it into an input stream.
3.  This stream is passed to a main processor (e.g., `GameProcessor`).
4.  The `GameProcessor` acts as a router, directing the stream to a specialized sub-processor based on the request's "action".
5.  The sub-processor executes its logic, which involves formatting a prompt and calling the Gemini model via a `genai_model.GenaiModel` instance.
6.  The final text or data is yielded back through the stream, received by the route handler, and sent as an HTTP response.

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

## 3. Core AI Techniques in Action

This section details the specific AI prompting techniques used throughout the application, with code examples from the processors.

### A. Prompt Engineering & Grounding

**Prompt engineering** is the art of crafting precise instructions for the AI to get the desired output. **Grounding** is a key part of this, where we provide the AI with a clear role, context, and constraints to prevent it from deviating.

The `AnswerEvaluatorProcessor` is a perfect example. We don't just ask "Is this right?"; we give the model a persona ("You are an expert..."), provide the exact data to compare, and strictly define the output format ("Respond ONLY with 'Correct' or 'Incorrect'").

```python
# @/processors/answer_evaluator.py - A Grounded System Prompt

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
```
This highly-structured prompt significantly improves the reliability of the AI's evaluation.

### B. Few-Shot Prompting

**Few-shot prompting** (or in this case, one-shot) involves giving the model an example of the exact input/output format you want. This helps the model understand the task better than just an instruction alone. We use this for most of our translation challenges.

Notice the `Example:` in the prompt. This single example dramatically improves the consistency of the AI's output.

```python
# @/processors/challenge_generator.py - One-Shot Prompts

# ...
"kin_to_eng_proverb": (
    "Provide a {level} Kinyarwanda proverb that is relevant to Rwandan culture or values, and its English translation, separated by a pipe (|). "
    "Example: 'Akabando k\'iminsi gacibwa kare|A walking stick for old age is prepared in advance'. No other text."
),
"eng_to_kin_phrase": (
    "Provide a simple {level} English phrase that a tourist in Rwanda might use (e.g., asking for directions, ordering food, greeting someone), and its Kinyarwanda translation, separated by a pipe (|). "
    "Example: 'Where is the bathroom?|Bwihereho ni he?'. No other text."
),
# ...
```

### C. Retrieval-Augmented Generation (RAG) for Cultural Context

For the "Sakwe Sakwe" (riddle) game mode, using an AI to generate riddles from scratch would risk losing cultural authenticity. Instead, we use **Retrieval-Augmented Generation (RAG)**.

The "retrieval" step is simple but effective: we retrieve a real, culturally vetted riddle from a curated JSON file. The "augmentation" step happens when we later ask the AI to generate a *hint* for that specific riddle, augmenting the retrieved data with AI-generated assistance.

**Step 1: Retrieval from a Curated Source**

```python
# @/processors/challenge_generator.py - Retrieving a Riddle

def _load_riddles(self) -> list:
    try:
        with open("riddles.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# ... inside _generate_challenge_logic ...
if game_mode == "sakwe":
    if not self.ibisakuzo_examples: 
        return {"error_message": "Riddle database is empty."}
    
    # This is the "Retrieval" step.
    riddle_data = random.choice(self.ibisakuzo_examples)
    
    return {
        "challenge_type": "gusakuza_init", 
        "source_text": "Sakwe sakwe!", 
        "target_text": f"{riddle_data['riddle']}|{riddle_data['answer']}", 
        # ...
    }
```

```json
# @/riddles.json - A Snippet of our Curated Data

[
  {"riddle": "Kwa Bukoco barakocagurana", "answer": "Urusyo n'ingasire."},
  {"riddle": "Igira inyuma y'inzu uce inkoni y'umuze n'umunzenzi", "answer": "Urusogo n'urusogi."},
  ...
]
```
This ensures the riddles are authentic. The AI is then used for a task it's better suited for: providing helpful hints.

### D. JSON Output Control

To create the multi-chapter story mode, we need the AI to output a well-structured JSON object. We achieve this by explicitly instructing the model in the prompt about the desired format.

```python
# @/processors/challenge_generator.py - Forcing JSON Output

"story_creation": (
    "Write a short, engaging story for a language learning game about a tourist exploring a specific landmark or cultural site in Rwanda... "
    "The story should be broken into 3 chapters... "
    "Output a JSON object with a 'title' and a list of 'chapters' (strings). "
    "Do not add any other text, titles, or formatting."
),
```
This prompt is highly effective at making the model's response programmatically parsable, which is essential for creating the stateful story mode.

### E. Multimodality: Combining Text and Images

The `genai-processors` library makes handling multimodal input (like text and images) straightforward. In the `ChallengeGeneratorProcessor`, we create a list of `ProcessorPart` objects—one for the text prompt and one for the image—and stream them to the model.

```python
# @/processors/challenge_generator.py - Multimodal Input

async def _run_text_processor(self, processor_input: Dict[str, Any], prompt_key: str) -> str:
    prompt = self.prompts[prompt_key]
    log_prompt = prompt.format(**processor_input)
    logger.info(f"\n--- GenAI-Processor REQUEST ---\nPROMPT: {log_prompt}\n")

    for model_name in self.model_names:
        try:
            processor = genai_model.GenaiModel(model_name=model_name, api_key=self.api_key)
            response = ""
            
            # Create a list of parts for multimodal input
            parts = [ProcessorPart(log_prompt)]
            if "image" in processor_input:
                parts.append(ProcessorPart(processor_input["image"]))
            
            # The library handles sending the multiple parts correctly
            input_stream = streams.stream_content(parts)
            async for part in processor(input_stream):
                if part.text:
                    response += part.text
            
            logger.info(f"\n--- GenAI-Processor RESPONSE (model: {model_name}) ---\nRESPONSE: {response}\n")
            return response
        # ...
```
This clean interface allows us to build complex, multimodal challenges without getting bogged down in the details of formatting multipart requests.

---
This guide should provide a solid foundation for understanding how **Bavuga Ntibavuga** leverages the `genai-processors` library and advanced prompting techniques to create a rich, AI-powered educational experience. Happy coding!