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
)
import context
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor
from processors.game_logic.game_processor import GameProcessor

# --- Argument Parsing and App Mode Initialization ---
parser = argparse.ArgumentParser(description="Bavuga_Nti_bavuga Language App")
parser.add_argument("--dev", action="store_true", help="Run in development mode.")
parser.add_argument("--debug", action="store_true", help="Enable detailed debug logging.")
args = parser.parse_args()

init_app_mode(args.dev)

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
if not args.debug:
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

# --- Constants ---
GEMINI_MODEL_NAME = "gemini-1.5-flash"
GEMINI_TTS_MODEL_NAME = "gemini-1.5-flash-tts"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
IMAGE_DIR = "sampleimg"

from api.models import ChallengeResponse, SubmissionResponse, TranscribeResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan event started.")
    if not DEV_MODE:
        await connect_to_mongo()
    
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    context.challenge_generator = ChallengeGeneratorProcessor(GEMINI_MODEL_NAME)
    context.answer_evaluator = AnswerEvaluatorProcessor(GEMINI_MODEL_NAME)
    context.game_processor = GameProcessor(context.challenge_generator, context.answer_evaluator)

    if DEV_MODE:
        logger.info("Running in DEV mode. Initializing Gemini-powered audio processors.")
        context.stt_processor = create_gemini_speech_to_text_processor(GEMINI_MODEL_NAME)
        context.tts_processor = create_gemini_text_to_speech_processor(GEMINI_TTS_MODEL_NAME)
    else:
        logger.info("Running in PROD mode. Initializing Google Cloud audio clients.")
        if not GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT not found for Production mode.")
        # Assuming you have these functions defined elsewhere
        # context.stt_processor = create_google_speech_to_text_processor(GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION)
        # context.tts_processor = create_google_text_to_speech_processor()
    
    yield
    
    if not DEV_MODE:
        await close_mongo_connection()

def create_app():
    app = FastAPI(lifespan=lifespan)

    # --- Mount Static Files and API Routers ---
    if os.path.exists(IMAGE_DIR):
        app.mount(f"/{IMAGE_DIR}", StaticFiles(directory=IMAGE_DIR), name="static_images")
    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(http_routes.router)
    app.include_router(websocket_routes.router)
    
    return app

app = create_app()

# --- Main Execution ---
if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=2500)
    except (ValueError, KeyError) as e:
        logger.critical(e, exc_info=True)
        exit(1)
