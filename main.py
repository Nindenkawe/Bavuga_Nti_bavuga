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

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
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
    DEV_MODE
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

# --- Load Riddles ---
IBISAKUZO_EXAMPLES = []
try:
    with open("riddles.json", "r") as f:
        IBISAKUZO_EXAMPLES = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logger.warning(f"Could not load riddles.json: {e}. Dev mode riddles will be static.")

# --- AI & Cloud Client Initialization ---
api_key = os.getenv("GEMINI_API_KEY")
model = None
speech_client = None
tts_client = None

def initialize_clients(dev_mode: bool):
    global model, speech_client, tts_client
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMMA_MODEL_NAME)
            logger.info("Gemini AI model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI model: {e}")
    else:
        logger.warning("GEMINI_API_KEY not found, core AI features will be disabled.")

    if not dev_mode:
        try:
            from google.cloud import speech, texttospeech
            speech_client = speech.SpeechClient()
            tts_client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud Audio clients initialized successfully for Production Mode.")
        except (ImportError, Exception) as e:
            logger.warning(f"Could not initialize Google Cloud Audio clients: {e}. Production audio features will be disabled.")

# --- FastAPI App Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # The app mode is initialized before uvicorn runs, so DEV_MODE is set.
    if not DEV_MODE:
        await connect_to_mongo()
    yield
    if not DEV_MODE:
        await close_mongo_connection()

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

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

# --- Generative AI & Mock Functions ---
async def generate_challenge_dev(difficulty: int, state: GameState, game_mode: str = "translation") -> dict:
    """Generates a static challenge for development mode."""
    await asyncio.sleep(0.05) # Simulate async call

    if game_mode == "riddles":
        challenge_type = "gusakuza"
    elif game_mode == "image":
        challenge_type = "image_description"
    else: # translation
        challenge_type = random.choice(["kin_to_eng_proverb", "eng_to_kin_phrase"])

    if challenge_type == "gusakuza":
        if IBISAKUZO_EXAMPLES:
            riddle_data = random.choice(IBISAKUZO_EXAMPLES)
            target_text = f"{riddle_data['riddle']}|{riddle_data['answer']}"
        else:
            target_text = "Igisakuzo|Some Answer" # Fallback
        return {
            "challenge_type": "gusakuza_init",
            "source_text": "Sakwe sakwe!",
            "target_text": target_text,
            "context": "Reply with 'soma' to get the riddle.",
        }
    elif challenge_type == "image_description":
        return {
            "challenge_type": challenge_type,
            "source_text": "https://picsum.photos/seed/picsum/200/300",
            "target_text": "A random image",
            "context": "This is a development mode image challenge.",
        }
    else:
        return {
            "challenge_type": challenge_type,
            "source_text": f"Dev mode source text ({challenge_type})",
            "target_text": "Dev mode target text",
            "context": "This is a development mode challenge.",
        }

async def evaluate_answer_dev(user_answer: str, target_text: str, challenge_type: str) -> bool:
    # ... (existing mock function, no changes needed)
    await asyncio.sleep(0.05)
    return user_answer.lower() == target_text.lower()

async def generate_challenge(difficulty: int, state: GameState) -> dict:
    if DEV_MODE or not model:
        return await generate_challenge_dev(difficulty, state)
    # ... (rest of the function is the same)
    try:
        level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(difficulty, "intermediate")
        challenge_types = ["kin_to_eng_proverb", "eng_to_kin_phrase", "gusakuza"]
        if state.score > 50 and state.lives > 1 and random.random() < 0.3:
            challenge_types.append("image_description")
        challenge_type = random.choice(challenge_types)

        if challenge_type == "gusakuza":
            prompt = "Generate a Kinyarwanda riddle (igisakuzo). The response should be in the format 'riddle|answer'."
            if IBISAKUZO_EXAMPLES:
                examples = random.sample(IBISAKUZO_EXAMPLES, min(len(IBISAKUZO_EXAMPLES), 3))
                example_text = "\n".join([f"Example: {ex['riddle']} | {ex['answer']}" for ex in examples])
                prompt += f"\nHere are some examples:\n{example_text}"
        else:
            prompt = f"Generate a {challenge_type} challenge for a {level} user."

        if state.incorrect_answers:
            prompt += f" Consider these previous incorrect answers: {', '.join(state.incorrect_answers)}"

        for attempt in range(MAX_RETRIES):
            try:
                response = await model.generate_content_async(prompt)
                parts = response.text.split('|')
                if len(parts) >= 2:
                    # If the response is valid, break the loop
                    break
                else:
                    logger.warning(f"Attempt {attempt + 1} of {MAX_RETRIES}: Invalid response format from agent. Retrying...")
                    await asyncio.sleep(BASE_DELAY * (attempt + 1))
            except Exception as e:
                logger.error(f"An exception occurred during challenge generation on attempt {attempt + 1}: {e}")
                await asyncio.sleep(BASE_DELAY * (attempt + 1))
        else:
            # This else block runs if the loop completes without a 'break'
            logger.error(f"Failed to get a valid response from agent after {MAX_RETRIES} attempts.")
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
                "challenge_type": "gusakuza_init",
                "source_text": "Sakwe sakwe!",
                "target_text": response.text,
                "context": "Reply with 'soma' to get the riddle.",
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
            "error_message": "AI service is currently down. Please try again later."
        }

async def evaluate_answer(user_answer: str, target_text: str, challenge_type: str) -> bool:
    if DEV_MODE or not model:
        return await evaluate_answer_dev(user_answer, target_text, challenge_type)
    # ... (rest of the function is the same)
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
                f"Consider common synonyms and minor grammatical variations. Respond ONLY with 'Correct' or 'Incorrect'."
            )
        response = await model.generate_content_async(prompt)
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
    audio_features_enabled = (DEV_MODE and model is not None) or (tts_client is not None and speech_client is not None)
    return templates.TemplateResponse("index.html", {"request": request, "total_score": total_score, "lives": current_state.lives, "score": current_state.score, "dev_mode": DEV_MODE, "audio_features_enabled": audio_features_enabled})

@app.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(difficulty: int = 1, game_mode: str = "translation"):
    if not model and not DEV_MODE:
        raise HTTPException(status_code=503, detail="Core AI service is not available. Check GEMINI_API_KEY.")
    current_state = await get_game_state()
    current_state.game_mode = game_mode
    await update_game_state(current_state)
    challenge_data = await generate_challenge(difficulty, current_state, game_mode)

    if "error_message" in challenge_data:
        raise HTTPException(status_code=503, detail=challenge_data["error_message"])

    if challenge_data["challenge_type"] == "gusakuza_init":
        current_state.pending_riddle = challenge_data["target_text"]
        await update_game_state(current_state)
        return ChallengeResponse(
            challenge_id="gusakuza_init",
            source_text=challenge_data["source_text"],
            context=challenge_data["context"],
            challenge_type="gusakuza_init"
        )

    challenge = Challenge(**challenge_data, difficulty=difficulty)
    challenge_id = await save_challenge(challenge)
    
    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type
    )

@app.post("/soma", response_model=ChallengeResponse)
async def soma_endpoint():
    # ... (endpoint logic remains the same)
    current_state = await get_game_state()
    if not current_state.pending_riddle:
        raise HTTPException(status_code=400, detail="No pending riddle found.")

    try:
        parts = current_state.pending_riddle.split('|')
        if len(parts) == 3:
            riddle = parts[1].strip()
            answer = parts[2].strip()
        elif len(parts) == 2:
            riddle = parts[0].strip()
            answer = parts[1].strip()
        else:
            logger.error(f"Invalid pending_riddle format: {current_state.pending_riddle}")
            raise ValueError("Invalid riddle format in game state.")
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid riddle format in game state.")

    challenge = Challenge(challenge_type="gusakuza", source_text=riddle.strip(), target_text=answer.strip(), difficulty=1, context="Igisakuzo")
    challenge_id = await save_challenge(challenge)
    current_state.pending_riddle = None
    await update_game_state(current_state)

    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type
    )

@app.post("/submit_answer", response_model=SubmissionResponse)
async def submit_answer_endpoint(challenge_id: str = Form(...), user_answer: str = Form(...)):
    # ... (endpoint logic remains the same)
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    is_correct = await evaluate_answer(user_answer, challenge.target_text, challenge.challenge_type)
    current_state = await get_game_state()
    
    if is_correct:
        current_state.score += POINTS_PER_CORRECT_ANSWER
        message = "Correct!"
        current_state.incorrect_answers = []
    else:
        current_state.lives -= 1
        message = "Incorrect."
        current_state.incorrect_answers.append(user_answer)

    score_awarded = POINTS_PER_CORRECT_ANSWER if is_correct else 0

    submission = Submission(challenge_id=PyObjectId(challenge_id), user_answer=user_answer, is_correct=is_correct, score=score_awarded)
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
        current_state.lives = 3
        current_state.score = 0
        current_state.incorrect_answers = []

    await update_game_state(current_state)
    return SubmissionResponse(**response_data)

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    if DEV_MODE:
        if not model:
            raise HTTPException(status_code=501, detail="Gemini AI not available for transcription in Dev Mode.")
        try:
            logger.info("Transcribing audio using Gemini in Dev Mode...")
            audio_blob = {
                'mime_type': audio_file.content_type,
                'data': await audio_file.read()
            }
            response = await model.generate_content_async(["Transcribe this Kinyarwanda audio:", audio_blob])
            return TranscribeResponse(transcript=response.text)
        except Exception as e:
            logger.error(f"Error during Gemini transcription: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to process audio with Gemini: {e}")
    else:
        if not speech_client:
            raise HTTPException(status_code=501, detail="Google Cloud Speech-to-Text not available.")
        try:
            logger.info("Transcribing audio using Google Cloud Speech-to-Text...")
            content = await audio_file.read()
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS, sample_rate_hertz=48000, language_code="rw-RW")
            response = speech_client.recognize(config=config, audio=audio)
            if not response.results or not response.results[0].alternatives:
                raise HTTPException(status_code=400, detail="Could not transcribe audio.")
            return TranscribeResponse(transcript=response.results[0].alternatives[0].transcript)
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to process audio: {e}")

@app.post("/synthesize")
async def synthesize_speech(text: str = Form(...)):
    if DEV_MODE:
        # Gemini does not generate audio, so this feature is disabled in dev mode.
        # We return an empty response to prevent breaking the frontend.
        logger.info("Speech synthesis is disabled in Dev Mode.")
        return Response(content=b"", media_type="audio/mpeg")
    else:
        if not tts_client:
            raise HTTPException(status_code=501, detail="Google Cloud Text-to-Speech not available.")
        try:
            logger.info("Synthesizing speech using Google Cloud Text-to-Speech...")
            from google.cloud import texttospeech
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(language_code="rw-RW", name="rw-RW-Standard-A")
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            return StreamingResponse(io.BytesIO(response.audio_content), media_type="audio/mpeg")
        except Exception as e:
            logger.error(f"Error during speech synthesis: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to synthesize speech: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bavuga_Nti_bavuga Language App")
    parser.add_argument("--dev", action="store_true", help="Run in development mode using a local JSON DB and Gemini for audio.")
    args = parser.parse_args()

    # Initialize components based on the mode
    init_app_mode(args.dev)
    initialize_clients(args.dev)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2500)