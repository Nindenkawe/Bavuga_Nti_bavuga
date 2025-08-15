import os
import logging
import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel

from api import http_routes, websocket_routes
from db_logic import connect_to_mongo, close_mongo_connection, init_app_mode, DEV_MODE
from processors.audio import (
    create_gemini_speech_to_text_processor,
    create_gemini_text_to_speech_processor,
    create_google_speech_to_text_processor,
    create_google_text_to_speech_processor,
)
import context
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor


# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---
GEMINI_MODEL_NAME = "gemini-1.5-flash"
GEMINI_TTS_MODEL_NAME = "gemini-1.5-flash-tts"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
IMAGE_DIR = "sampleimg"

# --- Pydantic Models (shared across routes) ---
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

class TranscribeResponse(BaseModel):
    transcript: str


def initialize_clients(dev_mode: bool):
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    context.challenge_generator = ChallengeGeneratorProcessor(GEMINI_MODEL_NAME)
    context.answer_evaluator = AnswerEvaluatorProcessor(GEMINI_MODEL_NAME)

    if dev_mode:
        logger.info("Running in DEV mode. Initializing Gemini-powered audio processors.")
        context.stt_processor = create_gemini_speech_to_text_processor(GEMINI_MODEL_NAME)
        context.tts_processor = create_gemini_text_to_speech_processor(GEMINI_TTS_MODEL_NAME)
    else:
        logger.info("Running in PROD mode. Initializing Google Cloud audio clients.")
        if not GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT not found for Production mode.")
        context.stt_processor = create_google_speech_to_text_processor(GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION)
        context.tts_processor = create_google_text_to_speech_processor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DEV_MODE:
        await connect_to_mongo()
    yield
    if not DEV_MODE:
        await close_mongo_connection()

app = FastAPI(lifespan=lifespan)

# --- Mount Static Files and API Routers ---
if os.path.exists(IMAGE_DIR):
    app.mount(f"/{IMAGE_DIR}", StaticFiles(directory=IMAGE_DIR), name="static_images")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(http_routes.router)
app.include_router(websocket_routes.router)

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
