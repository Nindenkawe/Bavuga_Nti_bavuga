import os
import google.generativeai as genai
import logging
import random
from typing import Optional
from contextlib import asynccontextmanager
import asyncio
import re

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel

from db_logic import (
    connect_to_mongo,
    close_mongo_connection,
    save_challenge,
    get_challenge,
    save_submission,
    get_total_score,
    Challenge,
    Submission,
    PyObjectId
)

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
GEMMA_MODEL_NAME = "gemini-1.5-flash-latest"
MAX_RETRIES = 3
BASE_DELAY = 1
POINTS_PER_CORRECT_ANSWER = 10

# --- Generative AI Configuration ---
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is required.")
genai.configure(api_key=api_key)

# --- FastAPI App Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# --- Pydantic Models ---
class ChallengeResponse(BaseModel):
    challenge_id: str
    source_text: str
    context: Optional[str] = None
    challenge_type: str

class SubmissionResponse(BaseModel):
    message: str
    is_correct: bool
    correct_answer: Optional[str] = None
    score_awarded: int
    new_total_score: int
    lives: int
    score: int

# --- Game State ---
game_state = {
    "lives": 3,
    "score": 0
}

# --- Custom Exceptions ---
class AIServiceError(Exception):
    """Custom exception for AI service failures."""
    pass

# --- Generative AI Functions ---
async def call_generative_api(func, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"API call failed or returned invalid format (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay:.2f}s.")
            await asyncio.sleep(delay)
    
    logger.error("AI service failed after multiple retries.")
    raise AIServiceError("AI service is unavailable after multiple retries.")

async def generate_challenge(difficulty: int, previous_answers: list[str] = None) -> dict:
    """Generates a new challenge using the AI, with a fallback mechanism."""
    try:
        return await call_generative_api(_generate_challenge_internal, difficulty, previous_answers)
    except AIServiceError:
        return {
            "challenge_type": "eng_to_kin_phrase",
            "source_text": "Service Unavailable",
            "target_text": "AI service is currently down. Please try again later.",
            "context": "We are unable to generate new challenges at this time.",
        }

async def _generate_challenge_internal(difficulty: int, previous_answers: list[str] = None) -> dict:
    """Internal logic for generating a challenge."""
    level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(difficulty, "intermediate")
    
    challenge_types = ["kin_to_eng_proverb", "eng_to_kin_phrase"]
    if game_state["score"] > 50 and game_state["lives"] > 1:
        if random.random() < 0.3:
            challenge_types.append("image_description")

    challenge_type = random.choice(challenge_types)

    system_instruction = '''You are a master of Kinyarwanda and English, an expert in linguistics, culture, and word games. 
    Your goal is to create engaging and educational challenges that adapt to the user's performance.
    - You will be given a difficulty level and a list of the user's previous (incorrect) answers.
    - Use the previous answers to understand the user's weak points and tailor the next challenge to help them improve.
    - Generate challenges that are not just translations, but also cultural insights, idiomatic expressions, and even visual descriptions.
    - Ensure a logical progression of difficulty. Avoid overly simplistic or impossibly difficult jumps.
    - Be creative and make the experience fun and rewarding!
    '''

    prompt_parts = [
        f"Difficulty: {level}",
    ]
    if previous_answers:
        prompt_parts.append("Consider the user's previous incorrect answers to tailor the challenge:")
        for ans in previous_answers:
            prompt_parts.append(f"- {ans}")

    if challenge_type == "image_description":
        image_url = "https://picsum.photos/seed/picsum/200/300"
        prompt_parts.append(f"Challenge: Describe the image at this URL in Kinyarwanda or English: {image_url}")
        prompt_parts.append("Format: Image URL | Description in Kinyarwanda | Description in English")
    elif challenge_type == "kin_to_eng_proverb":
        prompt_parts.append("Challenge: Generate a Kinyarwanda proverb, its English translation, and a brief context.")
        prompt_parts.append("Format: Kinyarwanda Proverb | English Translation | Context")
    else:  # eng_to_kin_phrase
        prompt_parts.append("Challenge: Generate an English phrase and its Kinyarwanda translation.")
        prompt_parts.append("Format: English Phrase | Kinyarwanda Translation")
    
    prompt_parts.append("\nIMPORTANT: Respond ONLY with the formatted text, without any additional explanations, introductions, or markdown.")
    full_prompt = "\n".join(prompt_parts)

    model = genai.GenerativeModel(GEMMA_MODEL_NAME, system_instruction=system_instruction)
    response = await model.generate_content_async(full_prompt)
    
    text = response.text.strip()
    match = re.search(r"^(.*?)\s*\|\s*(.*?)(?:\s*\|\s*(.*))?$", text, re.MULTILINE)

    if not match:
        logger.error(f"Could not parse AI response: {text}")
        raise ValueError("Invalid format from AI: No match found")

    parts = [p.strip() if p else "" for p in match.groups()]

    if challenge_type == "image_description" and len(parts) >= 2:
        return {
            "challenge_type": challenge_type,
            "source_text": parts[0],
            "target_text": f"Kinyarwanda: {parts[1]}\nEnglish: {parts[2]}",
            "context": "Describe the image in either language.",
        }
    elif challenge_type == "kin_to_eng_proverb" and len(parts) >= 3:
        return {
            "challenge_type": challenge_type,
            "source_text": parts[0],
            "target_text": parts[1],
            "context": parts[2],
        }
    elif challenge_type == "eng_to_kin_phrase" and len(parts) >= 2:
        return {
            "challenge_type": challenge_type,
            "source_text": parts[0],
            "target_text": parts[1],
            "context": None,
        }
    else:
        logger.error(f"Invalid format from AI for challenge type {challenge_type}: {text}")
        raise ValueError(f"Invalid format from AI after parsing: {text}")

async def evaluate_answer(user_answer: str, target_text: str) -> bool:
    """Evaluates the user's answer with AI assistance."""
    try:
        return await call_generative_api(_evaluate_answer_internal, user_answer, target_text)
    except AIServiceError:
        logger.error("AI service is unavailable to evaluate answer. Defaulting to incorrect.")
        return False

async def _evaluate_answer_internal(user_answer: str, target_text: str) -> bool:
    prompt = f'''You are an expert in Kinyarwanda and English. Evaluate if the user's answer is a correct and accurate translation of the target text. 
    Consider common synonyms and minor grammatical variations, but reject answers that are clearly wrong, incomplete, or irrelevant.
    
    User's Answer: '{user_answer}'
    Target Text: '{target_text}'
    
    Respond ONLY with 'Correct' or 'Incorrect'.'''
    model = genai.GenerativeModel(GEMMA_MODEL_NAME)
    response = await model.generate_content_async(prompt)
    return "correct" in response.text.strip().lower()

# --- API Endpoints ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    total_score = await get_total_score()
    return templates.TemplateResponse("index.html", {"request": request, "total_score": total_score, "lives": game_state["lives"], "score": game_state["score"]})

@app.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(difficulty: int = 1):
    previous_answers = game_state.get("incorrect_answers")
    challenge_data = await generate_challenge(difficulty, previous_answers)
    
    challenge = Challenge(
        **challenge_data,
        difficulty=difficulty
    )
    challenge_id = await save_challenge(challenge)
    
    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type
    )

@app.post("/submit_answer", response_model=SubmissionResponse)
async def submit_answer_endpoint(challenge_id: str = Form(...), user_answer: str = Form(...)):
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    is_correct = await evaluate_answer(user_answer, challenge.target_text)
    
    if is_correct:
        game_state["score"] += POINTS_PER_CORRECT_ANSWER
        message = "Correct!"
    else:
        game_state["lives"] -= 1
        message = "Incorrect."
        if "incorrect_answers" not in game_state:
            game_state["incorrect_answers"] = []
        game_state["incorrect_answers"].append(user_answer)

    score_awarded = POINTS_PER_CORRECT_ANSWER if is_correct else 0

    submission = Submission(
        challenge_id=PyObjectId(challenge_id),
        user_answer=user_answer,
        is_correct=is_correct,
        score=score_awarded
    )
    await save_submission(submission)

    new_total_score = await get_total_score()

    response_data = {
        "message": message,
        "is_correct": is_correct,
        "correct_answer": challenge.target_text,
        "score_awarded": score_awarded,
        "new_total_score": new_total_score,
        "lives": game_state["lives"],
        "score": game_state["score"]
    }

    if game_state["lives"] <= 0:
        response_data["message"] = "Game Over! You have no lives left."
        game_state["lives"] = 3
        game_state["score"] = 0
        game_state.pop("incorrect_answers", None)

    return SubmissionResponse(**response_data)

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)