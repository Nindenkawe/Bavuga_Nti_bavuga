import os
import logging
import random
from typing import Optional
from contextlib import asynccontextmanager
import asyncio
import re
import argparse
import json
import io

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
from genai_processors.processor import Processor

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
from processors.audio import (
    create_gemini_speech_to_text_processor,
    create_gemini_text_to_speech_processor,
    create_google_speech_to_text_processor,
    create_google_text_to_speech_processor,
)

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---
GEMINI_MODEL_NAME = "gemini-1.5-flash"
GEMINI_TTS_MODEL_NAME = "gemini-1.5-flash-tts" # Placeholder for a future model
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
POINTS_PER_CORRECT_ANSWER = 10
IMAGE_DIR = "sampleimg"

# --- AI & Cloud Client Initialization ---
challenge_generator: Optional[ChallengeGeneratorProcessor] = None
answer_evaluator: Optional[AnswerEvaluatorProcessor] = None
tts_processor: Optional[client.Processor] = None
stt_processor: Optional[client.Processor] = None

def initialize_clients(dev_mode: bool):
    global challenge_generator, answer_evaluator, tts_processor, stt_processor
    
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    challenge_generator = ChallengeGeneratorProcessor(GEMINI_MODEL_NAME)
    answer_evaluator = AnswerEvaluatorProcessor(GEMINI_MODEL_NAME)

    if dev_mode:
        logger.info("Running in DEV mode. Initializing Gemini-powered audio processors.")
        stt_processor = create_gemini_speech_to_text_processor(GEMINI_MODEL_NAME)
        tts_processor = create_gemini_text_to_speech_processor(GEMINI_TTS_MODEL_NAME)
    else:
        logger.info("Running in PROD mode. Initializing Google Cloud audio clients.")
        if not GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT not found for Production mode.")
        stt_processor = create_google_speech_to_text_processor(GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION)
        tts_processor = create_google_text_to_speech_processor()

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
    audio_features_enabled = tts_processor is not None and stt_processor is not None
    return templates.TemplateResponse("index.html", {"request": request, "total_score": total_score, "lives": current_state.lives, "score": current_state.score, "dev_mode": DEV_MODE, "audio_features_enabled": audio_features_enabled, "game_mode": current_state.game_mode})

@app.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(difficulty: int = 1, game_mode: str = None):
    if not challenge_generator:
        raise HTTPException(status_code=503, detail="Challenge generator not available.")
    
    current_state = await get_game_state()
    game_mode = game_mode or current_state.game_mode or "translation"
    current_state.game_mode = game_mode
    
    challenge_data = await challenge_generator.generate_challenge(difficulty, current_state, game_mode)
    
    if "error_message" in challenge_data:
        raise HTTPException(status_code=503, detail=challenge_data["error_message"])

    if challenge_data["challenge_type"] == "gusakuza_init":
        current_state.pending_riddle = challenge_data["target_text"]
        await update_game_state(current_state)
        return ChallengeResponse(challenge_id="gusakuza_init", **challenge_data)

    challenge = Challenge(**challenge_data, difficulty=difficulty)
    challenge_id = await save_challenge(challenge)
    await update_game_state(current_state)
    
    return ChallengeResponse(challenge_id=str(challenge_id), source_text=challenge.source_text, context=challenge.context, challenge_type=challenge.challenge_type)

@app.post("/soma", response_model=ChallengeResponse)
async def soma_endpoint():
    current_state = await get_game_state()
    if not current_state.pending_riddle:
        raise HTTPException(status_code=400, detail="No pending riddle.")
    
    riddle, answer = current_state.pending_riddle.split("|")
    challenge = Challenge(challenge_type="gusakuza", source_text=riddle.strip(), target_text=answer.strip(), difficulty=1, context="Igisakuzo")
    challenge_id = await save_challenge(challenge)
    current_state.pending_riddle = None
    await update_game_state(current_state)
    return ChallengeResponse(challenge_id=str(challenge_id), source_text=challenge.source_text, context=challenge.context, challenge_type=challenge.challenge_type)

@app.post("/submit_answer", response_model=SubmissionResponse)
async def submit_answer_endpoint(challenge_id: str = Form(...), user_answer: str = Form(...)):
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    current_state = await get_game_state()
    is_correct = False
    if any(keyword in user_answer.lower() for keyword in ["gitore", "ngicyo"]):
        message = "You gave up. The correct answer was:"
    else:
        is_correct = await answer_evaluator.evaluate_answer(user_answer, challenge.target_text, challenge.challenge_type)
        if is_correct:
            current_state.score += POINTS_PER_CORRECT_ANSWER
            message = "Correct!"
            if challenge.challenge_type == "gusakuza":
                current_state.thematic_words.append(challenge.target_text)
        else:
            current_state.lives -= 1
            message = "Incorrect."

    score_awarded = POINTS_PER_CORRECT_ANSWER if is_correct else 0
    await save_submission(Submission(challenge_id=PyObjectId(challenge_id), user_answer=user_answer, is_correct=is_correct, score=score_awarded))
    
    if current_state.lives <= 0:
        message = "Game Over! You have no lives left."
        current_state.lives = 3
        current_state.score = 0
    
    await update_game_state(current_state)
    new_total_score = await get_total_score()
    
    return SubmissionResponse(message=message, is_correct=is_correct, correct_answer=challenge.target_text, score_awarded=score_awarded, new_total_score=new_total_score, lives=current_state.lives, score=current_state.score)

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    if not stt_processor:
        raise HTTPException(status_code=503, detail="Speech-to-text service not available.")
    try:
        audio_data = await audio_file.read()
        transcript = await stt_processor.process_async({"audio": audio_data})
        return TranscribeResponse(transcript=transcript)
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise HTTPException(status_code=500, detail="Failed to transcribe audio.")

@app.post("/synthesize")
async def synthesize_speech(text: str = Form(...)):
    if not tts_processor:
        raise HTTPException(status_code=503, detail="Text-to-speech service not available.")
    try:
        # In dev mode, we might need to specify a voice if the model requires it
        input_data = {"text": text, "voice": "echo"} if DEV_MODE else {"text": text}
        audio_data = await tts_processor.process_async(input_data)
        return StreamingResponse(io.BytesIO(audio_data), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Error during synthesis: {e}")
        raise HTTPException(status_code=500, detail="Failed to synthesize speech.")

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bavuga_Nti_bavuga Language App")
    parser.add_argument("--dev", action="store_true", help="Run in development mode.")
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug logging.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    if not args.debug:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)

    try:
        init_app_mode(args.dev)
        initialize_clients(args.dev)
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=2500)
    except ValueError as e:
        logger.critical(e, exc_info=True)
        exit(1)