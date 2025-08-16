import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from processors.streaming_audio import StreamingAudioProcessor
from processors.mock_streaming_audio import MockStreamingAudioProcessor
import db_logic

router = APIRouter()

@router.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if db_logic.DEV_MODE:
        processor = MockStreamingAudioProcessor(websocket)
    else:
        processor = StreamingAudioProcessor(websocket)
    try:
        await processor.process_audio()
    except WebSocketDisconnect:
        print("Client disconnected from audio endpoint.")
