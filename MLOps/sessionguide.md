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

There are two primary ways to run this application, each suited for a different purpose.

### Path A: Development Mode (Recommended for UI/Frontend Work)
*   **Goal:** Run the application locally to work on the UI, game logic, or other features that do not require live audio transcription.
*   **How it Works:** In this mode, the application uses a **mock audio processor**. Instead of connecting to Google Cloud for speech-to-text, it returns simulated, pre-defined transcription data. This allows for rapid development without needing cloud credentials.
*   **Setup:**
    1.  Create a `.env` file and add your `GEMINI_API_KEY` (used for text-based AI features).
    2.  Install dependencies: `pip install -r requirements.txt`
    3.  Run the app: `./start.sh --dev`

### Path B: Production Mode (For Full Feature Testing & Deployment)
*   **Goal:** Run the complete, containerized application with all features enabled, including live audio transcription via Google Cloud and a persistent MongoDB database.
*   **Setup:**
    1.  Ensure Docker and Docker Compose are installed.
    2.  Fill out your `.env` file completely, including your Google Cloud Project ID.
    3.  Run the one-time cloud setup script to configure authentication: `./setup_gcloud.sh YOUR_PROJECT_ID`
    4.  Launch the application: `docker-compose up --build -d`

---

## 3. Core AI Techniques in Action

This section details the specific AI prompting techniques used throughout the application, with code examples from the processors.

### A. Prompt Engineering & Grounding

**Prompt engineering** is the art of crafting precise instructions for the AI to get the desired output. **Grounding** is a key part of this, where we provide the AI with a clear role, context, and constraints to prevent it from deviating. This is crucial for building reliable AI-powered features.

**How `genai-processors` Simplifies This:**
The library abstracts away the complexities of API calls. All the prompts are simple, formatted Python strings. This allows us to focus entirely on the creative and logical aspects of prompt design, rather than the technical overhead of making API requests. We can define our prompts in one place and use them throughout the application, making them easy to manage and reuse.

**Example 1: Strict Evaluation in `AnswerEvaluatorProcessor`**

The `AnswerEvaluatorProcessor` is a perfect example of a grounded prompt. We don't just ask "Is this right?"; we give the model a persona ("You are an expert..."), provide the exact data to compare, and strictly define the output format ("Respond ONLY with 'Correct' or 'Incorrect'").

```python
# @/processors/answer_evaluator.py - A Grounded System Prompt

self.prompt = (
    "You are an expert in Kinyarwanda and English. "
    "The target text is '{target_text}'. The user's answer is '{user_answer}'. "
    "Is the user's answer a correct translation? "
    "Consider synonyms and minor grammatical variations. "
    "Respond ONLY with 'Correct' or 'Incorrect'."
)
```
This highly-structured prompt significantly improves the reliability of the AI's evaluation, preventing it from giving conversational or ambiguous answers.

**Example 2: Forcing JSON Output in `ChallengeGeneratorProcessor`**

To create the multi-chapter story mode, we need the AI to output a well-structured JSON object. We achieve this by explicitly instructing the model in the prompt about the desired format.

```python
# @/processors/challenge_generator.py - Forcing JSON Output

"story_creation": (
    "Write a short, engaging story for a language learning game..."
    "The story should be broken into 3 chapters... "
    "Output a JSON object with a 'title' and a list of 'chapters' (strings). "
    "Do not add any other text, titles, or formatting."
),
```
This prompt is highly effective at making the model's response programmatically parsable, which is essential for creating the stateful story mode.

### B. Few-Shot Prompting

**Few-shot prompting** (or in this case, one-shot) involves giving the model an example of the exact input/output format you want. This helps the model understand the task better than just an instruction alone. We use this for most of our translation and description challenges.

**How `genai-processors` Simplifies This:**
Just like with grounding, the library lets us embed these examples directly into our prompt strings. We don't need to worry about special formatting for the examples or how to separate them from the main instruction. The library handles the communication with the model, so we can focus on providing clear and effective examples.

**Example 1: Translation Phrases in `ChallengeGeneratorProcessor`**

Notice the `Example:` in these prompts. This single example dramatically improves the consistency of the AI's output, ensuring it returns the data in the `source|target` format we expect.

```python
# @/processors/challenge_generator.py - One-Shot Prompts for Translation

"kin_to_eng_proverb": (
    "Provide a {level} Kinyarwanda proverb... and its English translation, separated by a pipe (|). "
    "Example: 'Akabando k\u0027iminsi gacibwa kare|A walking stick for old age is prepared in advance'. No other text."
),
"eng_to_kin_phrase": (
    "Provide a simple {level} English phrase... and its Kinyarwanda translation, separated by a pipe (|). "
    "Example: 'Where is the bathroom?|Bwihereho ni he?'. No other text."
),
```

**Example 2: Image Descriptions in `ChallengeGeneratorProcessor`**

We use the same one-shot technique for generating image descriptions, providing an example to guide the model's response style and format.

```python
# @/processors/challenge_generator.py - One-Shot Prompt for Image Description

"image_description": (
    "Describe this image of Rwanda in a single, descriptive sentence..."
    "Provide the description in both Kinyarwanda and English, separated by a pipe (|)..."
    "Example: 'Umusozi w\u0027u Rwanda ufite ibyiza nyaburanga|A Rwandan hill with beautiful scenery'. No other text."
),
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

## 4. Live Audio Streaming with WebSockets

The live transcription feature is a key part of the application, allowing users to speak their answers. This is achieved through a combination of browser-side audio capture, WebSockets for real-time communication, and a streaming-capable speech-to-text API on the backend.

### A. Client-Side: Capturing and Streaming Audio

The process begins in the user's browser. The `static/js/sakwe_client.js` file is responsible for:
1.  Requesting microphone access using `navigator.mediaDevices.getUserMedia`.
2.  Using the `MediaRecorder` API to capture audio.
3.  Sending small chunks of audio data to the server every second via a WebSocket connection.

```javascript
// @/static/js/sakwe_client.js - Streaming Audio from the Browser

function startMicrophone() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(event.data);
                }
            };

            mediaRecorder.start(1000); // Send audio data every 1 second
        })
        // ...
}
```

### B. Server-Side: Handling the WebSocket Connection

On the server, FastAPI handles the WebSocket connection in `api/websocket_routes.py`. This route is responsible for deciding which audio processor to use based on the application's mode (dev or production).

```python
# @/api/websocket_routes.py - Routing to the Correct Processor

@router.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if db_logic.DEV_MODE:
        processor = MockStreamingAudioProcessor(websocket)
    else:
        processor = StreamingAudioProcessor(websocket)
    try:
        await processor.process_audio()
    except WebSocketDisconnect:
        print("Client disconnected from audio endpoint.")
```

### C. Backend Processing: Real vs. Mock Transcription

This is where the actual speech-to-text processing happens.

**In Production Mode**, the `StreamingAudioProcessor` receives the audio chunks and forwards them to the Google Cloud Speech-to-Text API. This provides a true live transcription experience.

```python
# @/processors/streaming_audio.py - Live Transcription with Google Cloud

class StreamingAudioProcessor:
    # ...
    async def process_audio(self):
        requests = self.audio_generator()
        responses = self.client.streaming_recognize(
            config=self.streaming_config,
            requests=requests,
        )

        async for response in responses:
            for result in response.results:
                # ... send transcription back to client ...
```

**In Development Mode**, to avoid the need for cloud credentials, the `MockStreamingAudioProcessor` is used. It simply receives the audio chunks and sends back pre-defined, random text, allowing for easy testing of the UI and application flow.

```python
# @/processors/mock_streaming_audio.py - Mock Transcription for Development

class MockStreamingAudioProcessor:
    # ...
    async def process_audio(self):
        while True:
            try:
                _ = await self.websocket.receive_bytes()
                transcription = random.choice(self.mock_transcriptions)
                await self.websocket.send_text(f"Mock: {transcription}")
                await asyncio.sleep(2)
            # ...
```
This dual-processor approach is a powerful pattern for developing applications that rely on external services, providing a seamless and efficient development experience.

---
This guide should provide a solid foundation for understanding how **Bavuga Ntibavuga** leverages the `genai-processors` library and advanced prompting techniques to create a rich, AI-powered educational experience. Happy coding!
