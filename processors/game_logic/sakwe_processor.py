import asyncio
from enum import Enum, auto
import random
import logging

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

    def _load_riddles(self):
        # In a real application, this would load from a file or database.
        return [
            {"riddle": "Inshyushyu y'umusambi", "answer": "amazi"},
            {"riddle": "Abakobwa banjye bangana bose", "answer": "inkuyo"},
        ]

    async def _process_audio(self, audio_data: bytes) -> str:
        """Converts audio to text using the STT processor."""
        transcript_parts = await processor.apply_async(self.stt, [content_api.ProcessorPart(audio=audio_data)])
        return "".join(part.text for part in transcript_parts if part.text).lower().strip()

    async def speak(self, text: str):
        """Sends text to the TTS processor to be spoken to the user."""
        async for part in self.tts(streams.stream_content([text])):
            if part.audio:
                await self.output_queue.put(part)

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
                    riddle_data = random.choice(self.riddles)
                    self.current_riddle = riddle_data["riddle"]
                    self.current_answer = riddle_data["answer"]
                    self.state = GameState.WAITING_FOR_ANSWER
                    await self.speak(self.current_riddle)

            elif self.state == GameState.WAITING_FOR_ANSWER:
                if self.current_answer in transcript:
                    await self.speak("Correct!")
                    self.state = GameState.WAITING_FOR_SAKWE
                else:
                    await self.speak("Incorrect. Try again.")
        
        # This part is important for the processor protocol, even if we don't use it here.
        yield

    async def __call__(self, content: streams.AsyncIterable[content_api.ProcessorPart]) -> streams.AsyncIterable[content_api.ProcessorPart]:
        # We need a custom __call__ to handle the output queue
        asyncio.create_task(self.call(content))
        while True:
            yield await self.output_queue.get()
