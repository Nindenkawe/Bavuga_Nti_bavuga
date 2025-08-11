import os
import google.generativeai as genai
import logging
import random
from typing import Optional
from contextlib import asynccontextmanager
import asyncio
import re
from google_adk.agent import Agent
from google_adk.llm.gemini import Gemini

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
    get_game_state,
    update_game_state,
    Challenge,
    Submission,
    PyObjectId,
    GameState
)

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
GEMMA_MODEL_NAME = "gemini-2.5-flash-latest"
MAX_RETRIES = 3
BASE_DELAY = 1
POINTS_PER_CORRECT_ANSWER = 10

# --- Generative AI Configuration ---
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is required.")
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

# --- Custom Exceptions ---
class AIServiceError(Exception):
    """Custom exception for AI service failures."""
    pass

# --- AI Agent Configuration ---
agent = Agent(
    llm=Gemini(model=GEMMA_MODEL_NAME),
    persona=(
        "You are a master of Kinyarwanda and English, specializing in linguistics, "
        "culture, and word games for a Rwandan audience. Your goal is to create "
        "engaging and educational challenges that adapt to the user's performance."
    ),
)

# --- Generative AI Functions ---
async def generate_challenge(difficulty: int, state: GameState) -> dict:
    """Generates a new challenge using the AI agent."""
    try:
        level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(difficulty, "intermediate")
        
        challenge_types = ["kin_to_eng_proverb", "eng_to_kin_phrase", "gusakuza"]
        if state.score > 50 and state.lives > 1 and random.random() < 0.3:
            challenge_types.append("image_description")
        challenge_type = random.choice(challenge_types)

        if challenge_type == "gusakuza":
            prompt = "Generate a Kinyarwanda riddle (igisakuzo). The response should be in the format 'riddle|answer'."
        else:
            prompt = f"Generate a {challenge_type} challenge for a {level} user."

        if state.incorrect_answers:
            prompt += f" Consider these previous incorrect answers: {', '.join(state.incorrect_answers)}"

        response = await agent.chat(prompt)
        
        # Assuming the agent returns a parsable string
        parts = response.text.split('|')
        if len(parts) < 2:
            raise ValueError("Invalid response format from agent")

        if challenge_type == "image_description":
            return {
                "challenge_type": challenge_type,
                "source_text": parts[0].strip(),
                "target_text": f"Kinyarwanda: {parts[1].strip()}\nEnglish: {parts[2].strip() if len(parts) > 2 else ''}",
                "context": "Describe the image in either language.",
            }
        elif challenge_type == "kin_to_eng_proverb":
            return {
                "challenge_type": challenge_type,
                "source_text": parts[0].strip(),
                "target_text": parts[1].strip(),
                "context": parts[2].strip() if len(parts) > 2 else '',
            }
        elif challenge_type == "gusakuza":
            return {
                "challenge_type": challenge_type,
                "source_text": parts[0].strip(),
                "target_text": parts[1].strip(),
                "context": "Sakwe sakwe!",
            }
        else:  # eng_to_kin_phrase
            return {
                "challenge_type": challenge_type,
                "source_text": parts[0].strip(),
                "target_text": parts[1].strip(),
                "context": None,
            }

    except Exception as e:
        logger.error(f"Error generating challenge with agent: {e}")
        return {
            "challenge_type": "eng_to_kin_phrase",
            "source_text": "Service Unavailable",
            "target_text": "AI service is currently down. Please try again later.",
            "context": "We are unable to generate new challenges at this time.",
        }


async def evaluate_answer(user_answer: str, target_text: str, challenge_type: str) -> bool:
    """Evaluates the user's answer with the AI agent, using a tailored prompt."""
    try:
        if challenge_type == "gusakuza":
            prompt = (
                f"You are an expert in Kinyarwanda riddles (Ibisakuzo). The riddle's correct answer is '{target_text}'. "
                f"The user guessed '{user_answer}'. "
                f"Is the user's guess a correct or acceptable answer for this riddle? "
                f"Consider common variations and synonyms. Respond ONLY with 'Correct' or 'Incorrect'."
            )
        else:
            prompt = (
                f"You are an expert in Kinyarwanda and English. Evaluate if the user's answer '{user_answer}' "
                f"is a correct and accurate translation of the target text '{target_text}'. "
                f"Consider common synonyms and minor grammatical variations, but reject answers that are clearly wrong, "
                f"incomplete, or irrelevant. Respond ONLY with 'Correct' or 'Incorrect'."
            )
        response = await agent.chat(prompt)
        return "correct" in response.text.lower()
    except Exception as e:
        logger.error(f"Error evaluating answer with agent: {e}")
        return False



# --- API Endpoints ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    total_score = await get_total_score()
    current_state = await get_game_state()
    return templates.TemplateResponse("index.html", {"request": request, "total_score": total_score, "lives": current_state.lives, "score": current_state.score})

@app.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(difficulty: int = 1):
    current_state = await get_game_state()
    challenge_data = await generate_challenge(difficulty, current_state)
    
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

    is_correct = await evaluate_answer(user_answer, challenge.target_text, challenge.challenge_type)
    current_state = await get_game_state()
    
    if is_correct:
        current_state.score += POINTS_PER_CORRECT_ANSWER
        message = "Correct!"
        # On a correct answer, clear the list of incorrect ones for the next challenge generation
        current_state.incorrect_answers = []
    else:
        current_state.lives -= 1
        message = "Incorrect."
        current_state.incorrect_answers.append(user_answer)

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
        "lives": current_state.lives,
        "score": current_state.score
    }

    if current_state.lives <= 0:
        response_data["message"] = "Game Over! You have no lives left."
        # Reset game state for a new game
        current_state.lives = 3
        current_state.score = 0
        current_state.incorrect_answers = []

    await update_game_state(current_state)
    return SubmissionResponse(**response_data)

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)