import logging
from typing import TypedDict

from genai_processors.core import genai_model
from genai_processors import streams

logger = logging.getLogger(__name__)


class AnswerEvaluationInput(TypedDict):
    user_answer: str
    target_text: str
    challenge_type: str


class AnswerEvaluatorProcessor:
    def __init__(self, model_name: str):
        # Define the prompt template for the language evaluation
        self.prompt = (
            "You are an expert in Kinyarwanda and English. "
            "The target text is '{{target_text}}'. The user's answer is '{{user_answer}}'. "
            "Is the user's answer a correct translation? "
            "Consider synonyms and minor grammatical variations. "
            "Respond ONLY with 'Correct' or 'Incorrect'."
        )
        # Initialize the Gemini processor
        self.processor = genai_model.GenaiModel(model_name=model_name, prompt_template=self.prompt, temperature=0.1)

    async def evaluate_answer(
        self, user_answer: str, target_text: str, challenge_type: str
    ) -> bool:
        """Evaluates a user's answer using the Gemini processor."""
        # For riddles, the answer must be exact for cultural accuracy
        if challenge_type == "gusakuza":
            return user_answer.lower().strip() == target_text.lower().strip()

        try:
            # Create the input dictionary for the prompt
            input_data = AnswerEvaluationInput(
                user_answer=user_answer,
                target_text=target_text,
                challenge_type=challenge_type,
            )
            
            # Log the request
            logger.info(f"--- GenAI-Processor REQUEST ---\nPROMPT: {self.prompt.format(**input_data)}\n")

            # Asynchronously process the input to get the model's response
            response = ""
            input_stream = streams.stream_content([input_data])
            async for part in self.processor(input_stream):
                response += part.text
            
            # Log the response
            logger.info(f"--- GenAI-Processor RESPONSE ---\nRESPONSE: {response}\n")

            # The response from the processor is the raw text
            return response.strip().lower() == "correct"
        except Exception as e:
            logger.error(f"Error evaluating answer with processor: {e}")
            # Fallback to simple string matching in case of an API error
            return user_answer.lower().strip() == target_text.lower().strip()
