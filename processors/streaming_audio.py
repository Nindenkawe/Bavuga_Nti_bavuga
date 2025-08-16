# processors/streaming_audio.py

from google.cloud import speech

class StreamingAudioProcessor:
    def __init__(self, websocket):
        self.websocket = websocket
        self.client = speech.SpeechClient()
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="en-US",
            ),
            interim_results=True,
        )

    async def process_audio(self):
        requests = self.audio_generator()
        responses = self.client.streaming_recognize(
            config=self.streaming_config,
            requests=requests,
        )

        async for response in responses:
            for result in response.results:
                if result.is_final:
                    await self.websocket.send_text(f"Final: {result.alternatives[0].transcript}")
                else:
                    await self.websocket.send_text(f"Interim: {result.alternatives[0].transcript}")

    async def audio_generator(self):
        yield speech.StreamingRecognizeRequest(streaming_config=self.streaming_config)
        while True:
            chunk = await self.websocket.receive_bytes()
            if not chunk:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)
