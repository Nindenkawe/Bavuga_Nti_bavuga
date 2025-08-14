import os
import google.generativeai as genai
import logging
import random
from typing import Optional
from contextlib import asynccontextmanager
import asyncio
import re
import argparse
import json
from google.generativeai import GenerativeModel
from PIL import Image

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
import io

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
    GameState,
    init_app_mode,
    DEV_MODE,
)
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor

# --- Configuration ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Constants ---
GEMMA_MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 3
BASE_DELAY = 1
POINTS_PER_CORRECT_ANSWER = 10
IMAGE_DIR = "sampleimg"

# --- Load Riddles ---
IBISAKUZO_EXAMPLES = []
try:
    with open("riddles.json", "r") as f:
        IBISAKUZO_EXAMPLES = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logger.warning(
        f"Could not load riddles.json: {e}. Dev mode riddles will be static."
    )

# --- AI & Cloud Client Initialization ---
api_key = os.getenv("GEMINI_API_KEY")
model = None
speech_client = None
tts_client = None
challenge_generator = None
answer_evaluator = None


def initialize_clients(dev_mode: bool):
    global model, speech_client, tts_client, challenge_generator, answer_evaluator
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMMA_MODEL_NAME)
            logger.info("Gemini AI model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI model: {e}")
    else:
        logger.warning("GEMINI_API_KEY not found, core AI features will be disabled.")

    challenge_generator = ChallengeGeneratorProcessor(model, dev_mode)
    answer_evaluator = AnswerEvaluatorProcessor(model)

    if not dev_mode:
        try:
            from google.cloud import speech, texttospeech

            speech_client = speech.SpeechClient()
            tts_client = texttospeech.TextToSpeechClient()
            logger.info(
                "Google Cloud Audio clients initialized successfully for Production Mode."
            )
        except (ImportError, Exception) as e:
            logger.warning(
                f"Could not initialize Google Cloud Audio clients: {e}. Production audio features will be disabled."
            )


# --- FastAPI App Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DEV_MODE:
        await connect_to_mongo()
    yield
    if not DEV_MODE:
        await close_mongo_connection()


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
# Serve static images from the 'sampleimg' directory
if os.path.exists(IMAGE_DIR):
    app.mount(f"/{IMAGE_DIR}", StaticFiles(directory=IMAGE_DIR), name="static_images")

# --- Pydantic Models ---
class ChallengeResponse(BaseModel):
    challenge_id: str
    source_text: str
    context: Optional[str] = None
    challenge_type: str
    error_message: Optional[str] = None


class SubmissionResponse(BaseModel):
    message: str
    is_correct: bool
    correct_answer: Optional[str] = None
    score_awarded: int
    new_total_score: int
    lives: int
    score: int


class TranscribeResponse(BaseModel):
    transcript: str


# --- API Endpoints ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    total_score = await get_total_score()
    current_state = await get_game_state()
    audio_features_enabled = (DEV_MODE and model is not None) or (
        tts_client is not None and speech_client is not None
    )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "total_score": total_score,
            "lives": current_state.lives,
            "score": current_state.score,
            "dev_mode": DEV_MODE,
            "audio_features_enabled": audio_features_enabled,
            "game_mode": current_state.game_mode
        },
    )


@app.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(difficulty: int = 1, game_mode: str = None):
    if not model and not DEV_MODE:
        raise HTTPException(
            status_code=503,
            detail="Core AI service is not available. Check GEMINI_API_KEY.",
        )
    
    current_state = await get_game_state()
    
    # If no game mode is passed, use the last one from the state, or default to "translation"
    if game_mode is None:
        game_mode = current_state.game_mode or "translation"
    
    current_state.game_mode = game_mode
    
    challenge_data = await challenge_generator.generate_challenge(difficulty, current_state, game_mode)
    
    await update_game_state(current_state)

    if "error_message" in challenge_data:
        raise HTTPException(status_code=503, detail=challenge_data["error_message"])

    if challenge_data["challenge_type"] == "gusakuza_init":
        current_state.pending_riddle = challenge_data["target_text"]
        await update_game_state(current_state)
        return ChallengeResponse(
            challenge_id="gusakuza_init",
            source_text=challenge_data["source_text"],
            context=challenge_data["context"],
            challenge_type="gusakuza_init",
        )

    challenge = Challenge(**challenge_data, difficulty=difficulty)
    challenge_id = await save_challenge(challenge)

    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type,
    )



@app.post("/soma", response_model=ChallengeResponse)
async def soma_endpoint():
    current_state = await get_game_state()
    if not current_state.pending_riddle:
        raise HTTPException(status_code=400, detail="No pending riddle found.")

    try:
        riddle, answer = current_state.pending_riddle.split("|")
    except ValueError:
        logger.error(
            f"Invalid pending_riddle format: {current_state.pending_riddle}"
        )
        raise HTTPException(status_code=500, detail="Invalid riddle format in game state.")

    challenge = Challenge(
        challenge_type="gusakuza",
        source_text=riddle.strip(),
        target_text=answer.strip(),
        difficulty=1,
        context="Igisakuzo",
    )
    challenge_id = await save_challenge(challenge)
    current_state.pending_riddle = None
    await update_game_state(current_state)

    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type,
    )


class HintResponse(BaseModel):
    hint: str


@app.get("/get_hint", response_model=HintResponse)
async def get_hint_endpoint(challenge_id: str):
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    if challenge.challenge_type != "gusakuza":
        raise HTTPException(status_code=400, detail="Hints are only available for riddles.")

    if not model:
        raise HTTPException(status_code=503, detail="Core AI service is not available.")

    prompt = (
        f"The user is trying to solve the riddle: '{challenge.source_text}'. The answer is '{challenge.target_text}'. "
        f"Provide a clever, one-sentence hint that doesn't give away the answer."
    )

    logger.info(f"--- GEMINI API HINT REQUEST ---\nPROMPT: {prompt}\n")
    try:
        response = await model.generate_content_async(prompt)
        logger.info(f"--- GEMINI API HINT RESPONSE ---\nRESPONSE: {response.text}\n")
        return HintResponse(hint=response.text.strip())
    except Exception as e:
        logger.error(f"Error generating hint with agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate hint.")


@app.post("/submit_answer", response_model=SubmissionResponse)
async def submit_answer_endpoint(
    challenge_id: str = Form(...), user_answer: str = Form(...)
):

    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    current_state = await get_game_state()
    is_correct = False
    give_up_keywords = ["gitore", "ngicyo"]

    if any(keyword in user_answer.lower() for keyword in give_up_keywords):
        is_correct = False
        message = "You gave up. The correct answer was:"
    else:
        is_correct = await answer_evaluator.evaluate_answer(
            user_answer, challenge.target_text, challenge.challenge_type
        )
        if is_correct:
            current_state.score += POINTS_PER_CORRECT_ANSWER
            message = "Correct!"
            current_state.incorrect_answers = []
            # Add the answer to thematic words for the next round
            if challenge.challenge_type == "gusakuza":
                current_state.thematic_words.append(challenge.target_text)
        else:
            current_state.lives -= 1
            message = "Incorrect."
            current_state.incorrect_answers.append(user_answer)

    score_awarded = POINTS_PER_CORRECT_ANSWER if is_correct else 0
    submission = Submission(
        challenge_id=PyObjectId(challenge_id),
        user_answer=user_answer,
        is_correct=is_correct,
        score=score_awarded,
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
        "score": current_state.score,
    }

    if current_state.lives <= 0:
        response_data["message"] = "Game Over! You have no lives left."
        current_state.lives = 3
        current_state.score = 0
        current_state.incorrect_answers = []
        current_state.thematic_words = []

    await update_game_state(current_state)
    return SubmissionResponse(**response_data)


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    # This endpoint remains unchanged
    pass

@app.post("/synthesize")
async def synthesize_speech(text: str = Form(...)):
    # This endpoint remains unchanged
    pass

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bavuga_Nti_bavuga Language App")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode using a local JSON DB and Gemini for audio.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable detailed debug logging for Gemini API calls.",
    )
    args = parser.parse_args()

    # --- Configure Logging ---
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    # Silence other noisy loggers if needed
    if not args.debug:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)


    # Initialize components based on the mode
    init_app_mode(args.dev)
    initialize_clients(args.dev)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2500)
