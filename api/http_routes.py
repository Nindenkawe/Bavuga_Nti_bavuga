import os
import io
import json
import random
import logging
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, WebSocket, WebSocketDisconnect
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
)

router = APIRouter()
logger = logging.getLogger(__name__)
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
            "total_score": current_state.score,
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
    game_mode = game_mode or current_state.game_mode or "story"
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
        # The response is now a dictionary containing both the challenge and the updated state
        result_data = json.loads(response_json)
        challenge_data = result_data.get("challenge", {})
        updated_state_data = result_data.get("state")

        # Update the session with the new state returned by the processor
        if updated_state_data:
            current_state = db_logic.GameState(**updated_state_data)
            await update_game_state(request.session, current_state)

    except (json.JSONDecodeError, KeyError):
        # Fallback for image generation failure
        if game_mode == "image":
            logger.warning("Image generation failed, using fallback image.")
            fallback_image = random.choice(os.listdir("static/sampleimg"))
            challenge_data = {
                "challenge_type": "image_description",
                "source_text": f"/static/sampleimg/{fallback_image}",
                "target_text": "Describe the image.",
                "context": "Image Description",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to decode response from game processor.")

    if "error_message" in challenge_data:
        raise HTTPException(status_code=503, detail=challenge_data["error_message"])

    # Handle the 'sakwe' game mode initialization
    if challenge_data.get("challenge_type") == "gusakuza_init":
        current_state.pending_riddle = challenge_data["target_text"]
        await update_game_state(request.session, current_state)
        return ChallengeResponse(challenge_id="gusakuza_init", **challenge_data)

    # Save the challenge to the database
    challenge = Challenge(**challenge_data, difficulty=difficulty)
    challenge_id = await save_challenge(challenge)
    
    # The game state is already updated, so we don't need to call update_game_state again
    # unless there are other changes to be made here.

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


@router.get("/get_hint", response_model=dict)
async def get_hint_endpoint(request: Request, challenge_id: str):
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    if not context.game_processor:
        raise HTTPException(status_code=503, detail="Game processor not available.")

    current_state = await get_game_state(request.session)
    story_context = ""
    if current_state.story:
        try:
            story_data = json.loads(current_state.story)
            # Use the current chapter, but don't advance it
            story_context = story_data["chapters"][current_state.story_chapter]
        except (json.JSONDecodeError, IndexError):
            pass

    # The riddle is the source_text, and the answer is the target_text
    riddle = challenge.source_text
    answer = challenge.target_text

    hint_data = await context.game_processor.challenge_generator.generate_hint(riddle, answer, story_context)
    return hint_data


@router.post("/submit_answer", response_model=SubmissionResponse)
async def submit_answer_endpoint(
    request: Request, challenge_id: str = Form(...), user_answer: str = Form(...)
):
    challenge = await get_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    current_state = await get_game_state(request.session)
    
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
        eval_data = json.loads(response_json)
        is_correct = eval_data.get("is_correct", False)
        message = eval_data.get("feedback", "Could not get feedback.")
    except json.JSONDecodeError:
        is_correct = False
        message = "Error evaluating your answer."

    if is_correct:
        current_state.score += 10
        if challenge.challenge_type == "gusakuza":
            current_state.thematic_words.append(challenge.target_text)
        if current_state.score > 0 and current_state.score % 50 == 0 and not current_state.life_lost:
            game_modes = ["story", "translation", "sakwe", "image"]
            game_modes.remove(current_state.game_mode)
            current_state.game_mode = random.choice(game_modes)
            current_state.difficulty = min(3, current_state.difficulty + 1)
            message += f" You've unlocked a new game mode: {current_state.game_mode.capitalize()}! Difficulty increased."
    else:
        current_state.lives -= 1
        current_state.life_lost = True

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
        message = f"Game Over! You have no lives left. The correct answer was: {challenge.target_text}"
        current_state.lives = 3
        current_state.score = 0
        current_state.life_lost = False

    await update_game_state(request.session, current_state)

    return SubmissionResponse(
        message=message,
        is_correct=is_correct,
        correct_answer="", # This is now part of the feedback message
        score_awarded=score_awarded,
        new_total_score=current_state.score,
        lives=current_state.lives,
        score=current_state.score,
    )


@router.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    if not context.stt_processor:
        await websocket.close(code=1011, reason="Speech-to-text service not available.")
        return

    async def audio_stream_generator():
        while True:
            try:
                data = await websocket.receive_bytes()
                yield ProcessorPart(audio=data)
            except WebSocketDisconnect:
                break

    try:
        response_stream = context.stt_processor(audio_stream_generator())
        async for part in response_stream:
            if part.text:
                await websocket.send_text(part.text)
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
    finally:
        await websocket.close()


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
