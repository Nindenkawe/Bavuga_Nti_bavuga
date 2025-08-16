import logging
import os
from typing import TypedDict
import re

from genai_processors import processor
from genai_processors.core import genai_model
from genai_processors import streams
from genai_processors.content_api import ProcessorPart
import json
import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)


class AnswerEvaluationInput(TypedDict):
    user_answer: str
    target_text: str
    challenge_type: str


class AnswerEvaluatorProcessor(processor.Processor):
    def __init__(self, model_names: list[str]):
        self.model_names = model_names
        # Define the prompt template for the language evaluation
        self.prompt = (
            "You are an expert in Kinyarwanda and English. "
            "The target text is '{target_text}'. The user's answer is '{user_answer}'. "
            "Is the user's answer a correct translation? "
            "Consider synonyms and minor grammatical variations. "
            "Respond ONLY with 'Correct' or 'Incorrect'."
        )
        # Initialize the Gemini processor
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        self.api_key = api_key
    
    def _clean_text(self, text: str) -> str:
        """Removes punctuation, and extra whitespace and converts to lowercase."""
        return re.sub(r"[^\w\s]", "", text).lower().strip()

    async def call(
        self,
        input_stream: streams.AsyncIterable[ProcessorPart]
    ) -> streams.AsyncIterable[ProcessorPart]:
        """
        Processes the input stream to evaluate the user's answer.
        Expects a JSON string with 'user_answer', 'target_text', and 'challenge_type'.
        """
        input_json = ""
        async for part in input_stream:
            if part.text:
                input_json += part.text
        
        try:
            input_data = json.loads(input_json)
            user_answer = input_data["user_answer"]
            target_text = input_data["target_text"]
            challenge_type = input_data["challenge_type"]

            # For riddles, the answer must be exact for cultural accuracy
            if challenge_type == "gusakuza":
                is_correct = self._clean_text(user_answer) == self._clean_text(target_text)
                yield ProcessorPart(json.dumps({"is_correct": is_correct}))
                return

            # Create the input dictionary for the prompt
            prompt_input = AnswerEvaluationInput(
                user_answer=user_answer,
                target_text=target_text,
                challenge_type=challenge_type,
            )
            
            # Log the request
            formatted_prompt = self.prompt.format(**prompt_input)
            logger.info(f"--- GenAI-Processor REQUEST ---\nPROMPT: {formatted_prompt}\n")

            for model_name in self.model_names:
                try:
                    # Asynchronously process the input to get the model's response
                    response = ""
                    model = genai_model.GenaiModel(model_name=model_name, api_key=self.api_key)
                    model_input_stream = streams.stream_content([ProcessorPart(formatted_prompt)])
                    async for part in model(model_input_stream):
                        if part.text:
                            response += part.text
                    
                    # Log the response
                    logger.info(f"--- GenAI-Processor RESPONSE (model: {model_name}) ---\nRESPONSE: {response}\n")

                    is_correct = response.strip().lower() == "correct"
                    yield ProcessorPart(json.dumps({"is_correct": is_correct}))
                    return
                except Exception as e:
                    logger.error(f"Error evaluating answer with processor (model: {model_name}): {e}")
                    continue
            
            logger.error("All models failed. Falling back to simple string matching.")
            # Fallback to simple string matching in case of an API error
            is_correct = user_answer.lower().strip() == target_text.lower().strip()
            yield ProcessorPart(json.dumps({"is_correct": is_correct, "fallback": True}))


        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing input for evaluation: {e}")
            yield ProcessorPart(json.dumps({"error": "Invalid input format."}))

    async def evaluate_answer(
        self,
        user_answer: str,
        target_text: str,
        challenge_type: str
    ) -> bool:
        """
        Evaluates a user's answer using the Gemini processor.
        This is a convenience wrapper around the chain.
        """
        input_json = json.dumps({
            "user_answer": user_answer,
            "target_text": target_text,
            "challenge_type": challenge_type,
        })
        
        response_json = ""
        input_stream = streams.stream_content([ProcessorPart(input_json)])
        async for part in self(input_stream):
            if part.text:
                response_json += part.text
        
        try:
            response_data = json.loads(response_json)
            return response_data.get("is_correct", False)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response from evaluation chain.")
            return False

