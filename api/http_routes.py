import os
import io
import json
import random
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from genai_processors import streams, processor, content_api
from genai_processors.content_api import ProcessorPart

import db_logic
from db_logic import (
    save_challenge,
    get_challenge,
    save_submission,
    get_game_state,
    update_game_state,
    Challenge,
    Submission,
    PyObjectId,
)
import context
from api.models import (
    ChallengeResponse,
    SubmissionResponse,
    TranscribeResponse,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    current_state = await get_game_state(request.session)
    audio_features_enabled = context.tts_processor is not None and context.stt_processor is not None
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "total_score": current_state.score, # Use score from session
            "lives": current_state.lives,
            "score": current_state.score,
            "dev_mode": db_logic.DEV_MODE,
            "audio_features_enabled": audio_features_enabled,
            "game_mode": current_state.game_mode,
        },
    )


@router.get("/get_challenge", response_model=ChallengeResponse)
async def get_challenge_endpoint(request: Request, difficulty: int = None, game_mode: str = None):
    if not context.game_processor:
        raise HTTPException(status_code=503, detail="Game processor not available.")

    current_state = await get_game_state(request.session)
    game_mode = game_mode or current_state.game_mode or "translation"
    current_state.game_mode = game_mode
    difficulty = difficulty or current_state.difficulty

    input_data = {
        "action": "get_challenge",
        "difficulty": difficulty,
        "state": json.loads(current_state.model_dump_json(by_alias=True)),
        "game_mode": game_mode,
    }
    input_json = json.dumps(input_data)
    input_stream = streams.stream_content([ProcessorPart(input_json)])

    response_json = ""
    async for part in context.game_processor(input_stream):
        if part.text:
            response_json += part.text
    
    try:
        challenge_data = json.loads(response_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to decode response from game processor.")

    if "error_message" in challenge_data:
        raise HTTPException(status_code=503, detail=challenge_data["error_message"])

    if challenge_data["challenge_type"] == "gusakuza_init":
        current_state.pending_riddle = challenge_data["target_text"]
        await update_game_state(request.session, current_state)
        return ChallengeResponse(challenge_id="gusakuza_init", **challenge_data)

    challenge = Challenge(**challenge_data, difficulty=difficulty)
    challenge_id = await save_challenge(challenge)
    await update_game_state(request.session, current_state)

    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type,
    )


@router.post("/soma", response_model=ChallengeResponse)
async def soma_endpoint(request: Request):
    current_state = await get_game_state(request.session)
    if not current_state.pending_riddle:
        raise HTTPException(status_code=400, detail="No pending riddle.")

    riddle, answer = current_state.pending_riddle.split("|")
    challenge = Challenge(
        challenge_type="gusakuza",
        source_text=riddle.strip(),
        target_text=answer.strip(),
        difficulty=1,
        context="Igisakuzo",
    )
    challenge_id = await save_challenge(challenge)
    current_state.pending_riddle = None
    await update_game_state(request.session, current_state)
    return ChallengeResponse(
        challenge_id=str(challenge_id),
        source_text=challenge.source_text,
        context=challenge.context,
        challenge_type=challenge.challenge_type,
    )


@router.post("/submit_answer", response_model=SubmissionResponse)
async def submit_answer_endpoint(
    request: Request, challenge_id: str = Form(...), user_answer: str = Form(...)
):
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    current_state = await get_game_state(request.session)
    is_correct = False
    if any(keyword in user_answer.lower() for keyword in ["gitore", "ngicyo"]):
        message = "You gave up. The correct answer was:"
    else:
        input_data = {
            "action": "evaluate_answer",
            "user_answer": user_answer,
            "target_text": challenge.target_text,
            "challenge_type": challenge.challenge_type,
        }
        input_json = json.dumps(input_data)
        input_stream = streams.stream_content([ProcessorPart(input_json)])

        response_json = ""
        async for part in context.game_processor(input_stream):
            if part.text:
                response_json += part.text
        
        try:
            response_data = json.loads(response_json)
            is_correct = response_data.get("is_correct", False)
        except json.JSONDecodeError:
            is_correct = False # Fallback
            
        if is_correct:
            current_state.score += 10
            message = "Correct!"
            if challenge.challenge_type == "gusakuza":
                current_state.thematic_words.append(challenge.target_text)

            if current_state.score > 0 and current_state.score % 50 == 0:
                # Change game mode and increase difficulty
                game_modes = ["story", "translation", "sakwe", "image"]
                game_modes.remove(current_state.game_mode)
                current_state.game_mode = random.choice(game_modes)
                current_state.difficulty = min(3, current_state.difficulty + 1)
                message += f" You've unlocked a new game mode: {current_state.game_mode.capitalize()}! Difficulty increased."
        else:
            current_state.lives -= 1
            message = "Incorrect."

    score_awarded = 10 if is_correct else 0
    await save_submission(
        Submission(
            challenge_id=PyObjectId(challenge_id),
            user_answer=user_answer,
            is_correct=is_correct,
            score=score_awarded,
        )
    )

    if current_state.lives <= 0:
        message = "Game Over! You have no lives left."
        current_state.lives = 3
        current_state.score = 0

    await update_game_state(request.session, current_state)

    return SubmissionResponse(
        message=message,
        is_correct=is_correct,
        correct_answer=challenge.target_text,
        score_awarded=score_awarded,
        new_total_score=current_state.score,
        lives=current_state.lives,
        score=current_state.score,
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    if not context.stt_processor:
        raise HTTPException(
            status_code=503, detail="Speech-to-text service not available."
        )
    try:
        audio_data = await audio_file.read()
        result_parts = await processor.apply_async(
            context.stt_processor,
            [content_api.ProcessorPart(audio_data, mimetype=audio_file.content_type)],
        )
        transcript = "".join(part.text for part in result_parts if part.text)
        return TranscribeResponse(transcript=transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to transcribe audio.")


@router.post("/synthesize")
async def synthesize_speech(text: str = Form(...)):
    if not context.tts_processor:
        raise HTTPException(
            status_code=503, detail="Text-to-speech service not available."
        )
    try:
        result_parts = await processor.apply_async(
            context.tts_processor, [content_api.ProcessorPart(text)]
        )
        audio_data = b"".join(part.audio for part in result_parts if part.audio)
        return StreamingResponse(io.BytesIO(audio_data), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech.")
