That's an excellent idea. A `sessionguide.md` file will serve as a perfect script and reference for your talk. It will ensure you hit all the key points and provide clear, well-structured examples for your audience.

Here is the content for your `sessionguide.md` file, incorporating all the elements you requested.

-----

### **`sessionguide.md`**

# Session Guide: Building a Local-First Generative AI App

Welcome everyone\! Today, we're going to build and run a fun, educational Kinyarwanda vocabulary game called "Bavuga Ntibavuga" powered by the Gemini API. We'll focus on a local-first development workflow, using Docker Compose to run our entire application stack with a single command.

-----

## 1\. The Core Idea

"Bavuga Ntibavuga" is a language learning game that leverages generative AI to create dynamic challenges. Instead of static questions, our app uses the Gemini API to generate riddles, proverbs, and translation tasks in real-time.

-----

## 2\. Our Tech Stack

  * **Backend:** FastAPI (Python)
  * **Database:** MongoDB
  * **AI:** Gemini API via the `google_adk` library
  * **Containerization:** Docker Compose
  * **Frontend:** Vue.js (not covered in depth, but part of the full stack)

-----

## 3\. Getting Started

For this session, we'll use **GitHub Codespaces** to ensure a zero-setup environment for everyone. Just open the repository and click "Open in Codespaces."

We'll also be using the **Gemini-CLI** as our coding assistant. It's a fantastic tool that allows us to generate code snippets and solve problems directly from the terminal.

-----

## 4\. Dissecting the Code: The AI-Powered Backend

Let's dive into the most important parts of our `main.py` file, which handles all the backend logic.

### a) The AI Agent

We start by configuring a persona for our AI. This is a crucial step that tells Gemini what role to play, ensuring the challenges it generates are relevant and high-quality.

**`main.py` Snippet:**

```python
agent = Agent(
    llm=Gemini(model=GEMMA_MODEL_NAME),
    persona=(
        "You are a master of Kinyarwanda and English, specializing in linguistics, "
        "culture, and word games for a Rwandan audience. Your goal is to create "
        "engaging and educational challenges that adapt to the user's performance."
    ),
)
```

**Explanation:** This code snippet creates an `Agent` instance from the `google_adk` library, which provides a convenient, chat-focused interface to the Gemini API. We're telling the AI to act as a "master of Kinyarwanda and English," which will guide its responses.

### b) Generating a Challenge

The `generate_challenge` function is where the magic happens. It uses our AI agent to create a new, unique challenge based on the game's state (e.g., the user's difficulty level and past answers).

**`main.py` Snippet:**

```python
async def generate_challenge(difficulty: int, previous_answers: list[str] = None) -> dict:
    # ... (code for selecting challenge type)
    if challenge_type == "gusakuza":
        prompt = "Generate a Kinyarwanda riddle (igisakuzo). The response should be in the format 'riddle|answer'."
    else:
        prompt = f"Generate a {challenge_type} challenge for a {level} user."
        
    response = await agent.chat(prompt)
    
    # ... (code for parsing the response)
    
    return {
        "challenge_type": challenge_type,
        "source_text": parts[0].strip(),
        "target_text": parts[1].strip(),
        "context": parts[2].strip() if len(parts) > 2 else '',
    }
```

**Explanation:** We construct a specific prompt for our AI agent, telling it exactly what we need, like "Generate a Kinyarwanda riddle" or "Generate an `eng_to_kin_phrase`." We also specify the response format (`riddle|answer`) to make parsing the output easy.

**Example of Expected Response:**

  * **Prompt:** `Generate a gusakuza challenge. The response should be in the format 'riddle|answer'.`
  * **Expected AI Output:** `Ipfundo y'umusaza|urubuto rw'umwungu`
  * **Parsed into a Challenge:**
      * `challenge_type`: `gusakuza`
      * `source_text`: `Ipfundo y'umusaza`
      * `target_text`: `urubuto rw'umwungu`

### c) Evaluating the Answer

The `evaluate_answer` function uses Gemini again, this time to act as an expert judge. It takes the user's answer and the correct answer and determines if the user's response is accurate, even considering synonyms or minor variations.

**`main.py` Snippet:**

```python
async def evaluate_answer(user_answer: str, target_text: str) -> bool:
    prompt = f"You are an expert in Kinyarwanda and English. Evaluate if the user's answer '{user_answer}' is a correct and accurate translation of the target text '{target_text}'. Consider common synonyms and minor grammatical variations, but reject answers that are clearly wrong, incomplete, or irrelevant. Respond ONLY with 'Correct' or 'Incorrect'."
    response = await agent.chat(prompt)
    return "correct" in response.text.lower()
```

**Explanation:** The prompt here is very specific, instructing the AI to respond *only* with "Correct" or "Incorrect." This allows us to use a simple string check to get a reliable boolean result.

**Example of Expected Response:**

  * **`user_answer`**: `Umwana ni uw'uwo yibarutse`
  * **`target_text`**: `A child is one who gives birth to.`
  * **Expected AI Output:** `Incorrect`

-----

## 5\. Running the Application with Docker Compose

This is the final and most exciting part. Docker Compose allows us to run our entire application stack—the FastAPI backend and the MongoDB database—with a single command, making local development incredibly easy.

**`docker-compose.yml` Snippet:**

```dockercompose
# Set a project name to create shorter, predictable container/network names
name: bavuga-app

services:
  app: # Renamed from 'backend' for convention
    build: .
    container_name: bavuga-app # Explicit container name
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - MONGODB_URI=mongodb://database:27017 # Use the new service name 'database'
    depends_on:
      database:
        condition: service_healthy # Wait for the DB to be healthy

  database: # Renamed from 'db' for clarity
    image: mongo:latest
    container_name: bavuga-db # Explicit container name
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

volumes:
  mongo-data:
```

**Explanation:**

  * The `app` service builds our application from the current directory and exposes it on port `8000`.
  * It passes our `GEMINI_API_KEY` from our environment to the container, keeping it secure.
  * The `database` service uses the official `mongo:latest` image, and `volumes` ensures our data persists even if the container is restarted.
  * We've also added a `healthcheck` to the database. This is a best practice that ensures our `app` service only starts after the database is truly ready to accept connections.

To run everything, we simply use the command: `docker-compose up`.