import logging
import os
from typing import TypedDict, AsyncGenerator

from genai_processors.processor import Processor
from genai_processors import part_processor_function
from genai_processors.core import live_model
# from genai_processors.core import speech_to_text, text_to_speech
from genai_processors import content_api, streams
from genai_processors.content_api import ProcessorPart


logger = logging.getLogger(__name__)


class AudioInput(TypedDict):
    audio: bytes


class TextAndVoiceInput(TypedDict):
    text: str
    voice: str


# --- Gemini-powered processors for Dev Mode ---

def create_gemini_speech_to_text_processor(model_name: str) -> Processor:
    """Creates a speech-to-text processor using a Gemini model."""
    logger.info("Initializing Gemini speech-to-text processor...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    return live_model.LiveProcessor(
        model_name=model_name,
        api_key=api_key,
    )

def create_gemini_text_to_speech_processor(model_name: str) -> Processor:
    """Creates a text-to-speech processor using a Gemini model."""
    # This is a placeholder, as the library doesn't provide a direct Gemini TTS processor.
    # We'll simulate the behavior.
    @part_processor_function
    async def gemini_text_to_audio(part: ProcessorPart) -> AsyncGenerator[ProcessorPart, None]:
        if part.text:
            logger.info(f"DEV MODE (TTS): Simulating Gemini text-to-speech for: {part.text}")
            yield ProcessorPart(b"simulated audio data", mimetype="audio/mpeg")
    return gemini_text_to_audio


# --- Google Cloud processors for Production Mode ---

# def create_google_speech_to_text_processor(
#     project: str, location: str
# ) -> Processor:
#     """Creates a speech-to-text processor using Google Cloud Speech-to-Text.""" 
#     return speech_to_text.SpeechToText(
#         project=project,
#         location=location,
#         model="long",
#         language_codes=["en-US", "rw"],  # Kinyarwanda and English
#     )


# def create_google_text_to_speech_processor() -> Processor:
#     """Creates a text-to-speech processor using Google Cloud Text-to-Speech."""
#     return text_to_speech.TextToSpeech()