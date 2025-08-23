import os
import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel

from api import http_routes, websocket_routes
import db_logic
from db_logic import connect_to_mongo, close_mongo_connection, init_app_mode
from processors.audio import (
    create_gemini_speech_to_text_processor,
    create_gemini_text_to_speech_processor,
)
import context
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor
from processors.game_logic.game_processor import GameProcessor

# --- Configuration ---
load_dotenv()

# Determine run mode from environment variables
IS_DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

init_app_mode(IS_DEV_MODE)

# Configure logging with a specific format
log_level = logging.DEBUG if os.getenv("DEBUG_MODE", "false").lower() == "true" else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress verbose logging from Uvicorn and other libraries in non-debug mode
if not (os.getenv("DEBUG_MODE", "false").lower() == "true"):
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("genai_processors").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google.api_core").setLevel(logging.WARNING)
else:
    # In debug mode, let's get all the details
    logging.getLogger("genai_processors").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("google.api_core").setLevel(logging.DEBUG)


# --- Constants ---
GEMINI_DEV_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash", "imagen-2", "imagen-3"]
GEMINI_PROD_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash"]
GEMINI_TTS_MODEL_NAME = "gemini-2.5-flash"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
IMAGE_DIR = "sampleimg"

from api.models import ChallengeResponse, SubmissionResponse, TranscribeResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("="*20 + " Application Lifespan Start " + "="*20)
    logger.info(f"Running in {'DEV' if db_logic.DEV_MODE else 'PROD'} mode.")
    logger.debug(f"Debug mode is {'ENABLED' if os.getenv('DEBUG_MODE', 'false').lower() == 'true' else 'DISABLED'}.")

    # --- Database Connection ---
    if not db_logic.DEV_MODE:
        await connect_to_mongo()
    else:
        logger.info("Using development database file.")

    # --- API Key Check ---
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("CRITICAL: GEMINI_API_KEY not found in environment variables.")
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    else:
        logger.info("GEMINI_API_KEY found.")

    # --- Processor Initialization ---
    logger.info("Initializing core processors...")
    if db_logic.DEV_MODE:
        models = GEMINI_DEV_MODELS
    else:
        models = GEMINI_PROD_MODELS

    try:
        context.challenge_generator = ChallengeGeneratorProcessor(models)
        context.answer_evaluator = AnswerEvaluatorProcessor(models)
        context.game_processor = GameProcessor(context.challenge_generator, context.answer_evaluator)
        logger.info("Core processors initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize core processors: {e}", exc_info=True)
        raise

    # --- Audio Processor Initialization ---
    logger.info("Initializing audio processors...")
    if db_logic.DEV_MODE:
        logger.info("Initializing Gemini-powered audio processors for DEV mode.")
        try:
            context.stt_processor = create_gemini_speech_to_text_processor(GEMINI_DEV_MODELS[0])
            context.tts_processor = create_gemini_text_to_speech_processor(GEMINI_TTS_MODEL_NAME)
            logger.info("Gemini audio processors initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize Gemini audio processors: {e}", exc_info=True)
            raise
    else:
        logger.info("Initializing Google Cloud audio clients for PROD mode.")
        if not GOOGLE_CLOUD_PROJECT:
            logger.critical("GOOGLE_CLOUD_PROJECT not found for Production mode.")
            raise ValueError("GOOGLE_CLOUD_PROJECT not found for Production mode.")
        try:
            # Placeholder for actual Google Cloud client initialization
            # context.stt_processor = create_google_speech_to_text_processor(GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION)
            # context.tts_processor = create_google_text_to_speech_processor()
            logger.warning("PROD mode audio processors are not fully implemented yet.")
            # For now, we can use the Gemini processors to avoid crashing
            context.stt_processor = create_gemini_speech_to_text_processor(GEMINI_DEV_MODELS[0])
            context.tts_processor = create_gemini_text_to_speech_processor(GEMINI_TTS_MODEL_NAME)
            logger.info("Using fallback Gemini audio processors in PROD mode.")
        except Exception as e:
            logger.critical(f"Failed to initialize Google Cloud audio clients: {e}", exc_info=True)
            raise
            
    logger.info("All processors initialized.")
    logger.info("Application startup complete.")
    yield
    
    # --- Lifespan Shutdown ---
    logger.info("="*20 + " Application Lifespan Shutdown " + "="*20)
    if not db_logic.DEV_MODE:
        await close_mongo_connection()
    logger.info("Application shutdown complete.")

def create_app():
    app = FastAPI(lifespan=lifespan)

    # Add SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key=os.urandom(24))

    # --- Mount Static Files and API Routers ---
    if os.path.exists(IMAGE_DIR):
        app.mount(f"/{IMAGE_DIR}", StaticFiles(directory=IMAGE_DIR), name="static_images")
    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(http_routes.router)
    app.include_router(websocket_routes.router)
    
    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=IS_DEV_MODE,
        log_level=logging.getLevelName(logger.getEffectiveLevel()).lower(),
    )
