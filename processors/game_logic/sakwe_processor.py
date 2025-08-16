import asyncio
from enum import Enum, auto
import random
import logging
import json
import os
import re

from genai_processors import content_api
from genai_processors import processor
from genai_processors import streams

logger = logging.getLogger(__name__)


class GameState(Enum):
    WAITING_FOR_SAKWE = auto()
    WAITING_FOR_SOMA = auto()
    WAITING_FOR_ANSWER = auto()


class SakweProcessor(processor.Processor):
    def __init__(self, stt_processor: processor.Processor, tts_processor: processor.Processor):
        self.stt = stt_processor
        self.tts = tts_processor
        self.state = GameState.WAITING_FOR_SAKWE
        self.current_riddle = ""
        self.current_answer = ""
        self.riddles = self._load_riddles()
        self.output_queue = asyncio.Queue()
        self.seen_riddles = set()
        self.current_attempts = 0

    def _load_riddles(self):
        riddles_path = os.path.join(os.path.dirname(__file__), '..', '..', 'riddles.json')
        try:
            with open(riddles_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load riddles: {e}")
            return []

    def _is_answer_correct(self, user_answer: str) -> bool:
        """Checks if the user's answer is correct with flexible matching."""
        # Normalize the correct answer: lowercase, remove punctuation, split into words.
        normalized_correct = re.sub(r'[^\w\s]', '', self.current_answer.lower())
        correct_keywords = set(normalized_correct.split())

        # Normalize the user's answer: lowercase
        normalized_user = user_answer.lower()
        
        # Check if any of the keywords from the correct answer are in the user's answer.
        return any(keyword in normalized_user for keyword in correct_keywords)

    async def _process_audio(self, audio_data: bytes) -> str:
        """Converts audio to text using the STT processor."""
        transcript_parts = await processor.apply_async(self.stt, [content_api.ProcessorPart(audio_data, mimetype="audio/mpeg")])
        return "".join(part.text for part in transcript_parts if part.text).lower().strip()

    async def speak(self, text: str):
        """Sends text to the TTS processor to be spoken to the user."""
        async for part in self.tts(streams.stream_content([content_api.ProcessorPart(text)])):
            if part.audio:
                await self.output_queue.put(part)

    def _select_new_riddle(self):
        unseen_riddles = [r for r in self.riddles if r['riddle'] not in self.seen_riddles]
        if not unseen_riddles:
            self.seen_riddles.clear()
            unseen_riddles = self.riddles
        
        riddle_data = random.choice(unseen_riddles)
        self.current_riddle = riddle_data["riddle"]
        self.current_answer = riddle_data["answer"]
        self.seen_riddles.add(self.current_riddle)
        self.current_attempts = 0

    async def _get_hint(self, user_answer: str) -> str:
        # This is a placeholder for a call to the Gemini API.
        prompt = f"""
        You are a language tutor for a Rwandan game called "Sakwe Sakwe".
        Your role is to help the user guess the correct answer to a riddle.
        The user has up to 3 attempts.

        Current Riddle: "{self.current_riddle}"
        Correct Answer: "{self.current_answer}"
        User's Incorrect Answer: "{user_answer}"

        Please provide a helpful hint to guide the user to the correct answer.
        Do not reveal the answer. The hint should be in English.
        """
        # For this example, we'll return a static hint.
        return "That's not quite right. Try thinking about it from a different angle."

    async def call(self, input_stream: streams.AsyncIterable[content_api.ProcessorPart]) -> streams.AsyncIterable[content_api.ProcessorPart]:
        """The main game loop that processes incoming audio."""
        async for part in input_stream:
            if not part.audio:
                continue

            transcript = await self._process_audio(part.audio)
            if not transcript:
                continue

            logger.info(f"Heard: '{transcript}', State: {self.state.name}")

            if self.state == GameState.WAITING_FOR_SAKWE:
                if "sakwe" in transcript:
                    self.state = GameState.WAITING_FOR_SOMA
                    await self.speak("Soma!")

            elif self.state == GameState.WAITING_FOR_SOMA:
                if "soma" in transcript:
                    self._select_new_riddle()
                    self.state = GameState.WAITING_FOR_ANSWER
                    await self.speak(self.current_riddle)

            elif self.state == GameState.WAITING_FOR_ANSWER:
                if self._is_answer_correct(transcript):
                    await self.speak("Correct!")
                    self.state = GameState.WAITING_FOR_SAKWE
                else:
                    self.current_attempts += 1
                    if self.current_attempts >= 3:
                        await self.speak(f"The correct answer is {self.current_answer}. Let's try another one.")
                        self.state = GameState.WAITING_FOR_SAKWE
                    else:
                        hint = await self._get_hint(transcript)
                        await self.speak(hint)
        
        yield

    async def __call__(self, content: streams.AsyncIterable[content_api.ProcessorPart]) -> streams.AsyncIterable[content_api.ProcessorPart]:
        asyncio.create_task(self.call(content))
        while True:
            yield await self.output_queue.get()
