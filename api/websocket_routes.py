import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from genai_processors import content_api
from genai_processors import streams
from context import stt_processor, tts_processor
from processors.game_logic.sakwe_processor import SakweProcessor

router = APIRouter()

@router.websocket("/ws/sakwe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    sakwe_game = SakweProcessor(stt_processor, tts_processor)
    input_queue = asyncio.Queue()
    
    async def forward_to_client():
        """Listens for audio from the processor and sends it to the client."""
        output_stream = sakwe_game(streams.queue_to_stream(input_queue))
        async for part in output_stream:
            if part.audio:
                await websocket.send_bytes(part.audio)

    async def forward_from_client():
        """Receives audio from the client and sends it to the processor."""
        try:
            while True:
                audio_data = await websocket.receive_bytes()
                input_queue.put_nowait(content_api.ProcessorPart(audio=audio_data))
        except WebSocketDisconnect:
            print("Client disconnected from Sakwe endpoint.")

    # Run both forwarding tasks concurrently
    await asyncio.gather(forward_to_client(), forward_from_client())
