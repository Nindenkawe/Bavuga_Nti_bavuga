# processors/mock_streaming_audio.py

import asyncio
import random

class MockStreamingAudioProcessor:
    def __init__(self, websocket):
        self.websocket = websocket
        self.mock_transcriptions = [
            "This is a mock transcription.",
            "The quick brown fox jumps over the lazy dog.",
            "Testing the mock audio processor.",
            "Hello, world!",
            "This is a test."
        ]

    async def process_audio(self):
        while True:
            try:
                # We don't need to do anything with the received audio in mock mode
                _ = await self.websocket.receive_bytes()
                
                # Send a mock transcription back to the client
                transcription = random.choice(self.mock_transcriptions)
                await self.websocket.send_text(f"Mock: {transcription}")
                await asyncio.sleep(2)  # Simulate a delay
            except Exception as e:
                print(f"An error occurred: {e}")
                break
