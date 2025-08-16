import json
import logging
from typing import AsyncIterable

from genai_processors import processor
from genai_processors import streams
from genai_processors.content_api import ProcessorPart

from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor

logger = logging.getLogger(__name__)

class GameProcessor(processor.Processor):
    """A processor that routes requests to the appropriate game logic processor."""

    def __init__(self, challenge_generator: ChallengeGeneratorProcessor, answer_evaluator: AnswerEvaluatorProcessor):
        self.challenge_generator = challenge_generator
        self.answer_evaluator = answer_evaluator

    async def call(self, input_stream: AsyncIterable[ProcessorPart]) -> AsyncIterable[ProcessorPart]:
        input_json = ""
        async for part in input_stream:
            if part.text:
                input_json += part.text
        
        try:
            input_data = json.loads(input_json)
            action = input_data.get("action")

            if action == "get_challenge":
                # Pass the entire dictionary to the challenge generator
                chain_input_stream = streams.stream_content([ProcessorPart(json.dumps(input_data))])
                async for part in self.challenge_generator(chain_input_stream):
                    yield part
            
            elif action == "evaluate_answer":
                # Pass the entire dictionary to the answer evaluator
                chain_input_stream = streams.stream_content([ProcessorPart(json.dumps(input_data))])
                async for part in self.answer_evaluator(chain_input_stream):
                    yield part

            elif action == "get_hint":
                riddle = input_data.get("riddle")
                if not riddle:
                    yield ProcessorPart(json.dumps({"error": "Riddle not provided for hint."}));
                    return
                
                hint_data = await self.challenge_generator.generate_hint(riddle)
                yield ProcessorPart(json.dumps(hint_data))
            
            else:
                error_message = json.dumps({"error": "Invalid action specified."})
                yield ProcessorPart(error_message)

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing game logic request: {e}")
            error_message = json.dumps({"error": "Invalid input format for game processor."})
            yield ProcessorPart(error_message)
