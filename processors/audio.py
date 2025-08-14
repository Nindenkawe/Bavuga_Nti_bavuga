import logging
from typing import TypedDict, AsyncGenerator

from genai_processors.core.processor import Processor
from genai_processors.core import processor
from genai_processors.core.processors import speech_to_text, text_to_speech
from genai_processors.core import content_api
from genai_processors.core import streams


logger = logging.getLogger(__name__)


class AudioInput(TypedDict):
    audio: bytes


class TextAndVoiceInput(TypedDict):
    text: str
    voice: str


@processor
async def log_and_pass(text: str) -> AsyncGenerator[str, None]:
    """A simple processor to log the input and pass it through."""
    logger.info(f"DEV MODE (TTS): Synthesizing text: '{text[:30]}...'")
    yield text


# --- Gemini-powered processors for Dev Mode ---

def create_gemini_speech_to_text_processor(model_name: str) -> Processor:
    """Creates a speech-to-text processor using a Gemini model."""
    # This is a placeholder, as the library doesn't provide a direct Gemini STT processor
    # in the same way it does for Google Cloud.
    # We'll simulate the behavior.
    @processor
    async def gemini_audio_to_text(audio: content_api.Audio) -> AsyncGenerator[str, None]:
        logger.info("DEV MODE (STT): Simulating Gemini speech-to-text.")
        yield "simulated speech to text"
    return gemini_audio_to_text

def create_gemini_text_to_speech_processor(model_name: str) -> Processor:
    """Creates a text-to-speech processor using a Gemini model."""
    # This is a placeholder, as the library doesn't provide a direct Gemini TTS processor.
    # We'll simulate the behavior.
    @processor
    async def gemini_text_to_audio(text: str) -> AsyncGenerator[content_api.Audio, None]:
        logger.info(f"DEV MODE (TTS): Simulating Gemini text-to-speech for: {text}")
        yield content_api.Audio(data=b"simulated audio data")
    return log_and_pass | gemini_text_to_audio


# --- Google Cloud processors for Production Mode ---

def create_google_speech_to_text_processor(
    project: str, location: str
) -> Processor:
    """Creates a speech-to-text processor using Google Cloud Speech-to-Text."""
    return speech_to_text.SpeechToText(
        project=project,
        location=location,
        model="long",
        language_codes=["en-US", "rw"],  # Kinyarwanda and English
    )


def create_google_text_to_speech_processor() -> Processor:
    """Creates a text-to-speech processor using Google Cloud Text-to-Speech."""
    return text_to_speech.TextToSpeech()