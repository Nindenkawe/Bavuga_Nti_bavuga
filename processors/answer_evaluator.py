import logging
import os
from typing import TypedDict
import re
import json

from genai_processors import processor
from genai_processors.core import genai_model
from genai_processors import streams
from genai_processors.content_api import ProcessorPart

logger = logging.getLogger(__name__)


class AnswerEvaluationInput(TypedDict):
    user_answer: str
    target_text: str
    challenge_type: str


class AnswerEvaluatorProcessor(processor.Processor):
    def __init__(self, model_names: list[str]):
        self.model_names = model_names
        # Correctly define the multi-line prompt string using triple quotes.
        self.prompt = '''You are a friendly and encouraging Kinyarwanda language tutor.
Your goal is to provide helpful feedback to a student.
The correct answer is: '{target_text}'. The user's answer is: '{user_answer}'.
First, determine if the user's answer is correct. Consider synonyms and minor grammatical variations as correct.
Then, provide a brief, helpful feedback message.
If the answer is correct, give a short, positive confirmation.
If the answer is incorrect, gently correct them and provide the right answer.
Respond ONLY with a JSON object in the format: {"is_correct": true, "feedback": "your message here"}.
Do not add any other text or formatting.'''
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        self.api_key = api_key
    
    def _clean_text(self, text: str) -> str:
        """Removes punctuation, and extra whitespace and converts to lowercase."""
        # Remove punctuation using a more robust regex
        text = re.sub(r"[^\\w\\s]", "", text)
        # Normalize whitespace
        text = re.sub(r"\\s+", " ", text)
        return text.lower().strip()

    async def call(
        self,
        input_stream: streams.AsyncIterable[ProcessorPart]
    ) -> streams.AsyncIterable[ProcessorPart]:
        input_json = ""
        async for part in input_stream:
            if part.text:
                input_json += part.text
        
        try:
            input_data = json.loads(input_json)
            user_answer = input_data["user_answer"]
            target_text = input_data["target_text"]
            challenge_type = input_data["challenge_type"]

            # --- Simple Evaluation for definitive challenges ---
            if challenge_type in ["gusakuza", "story_translation", "kin_to_eng_proverb", "eng_to_kin_phrase"]:
                is_correct = self._clean_text(user_answer) == self._clean_text(target_text)
                if is_correct:
                    feedback = "Correct!"
                else:
                    feedback = f"Not quite. The correct answer is: {target_text}"
                yield ProcessorPart(json.dumps({"is_correct": is_correct, "feedback": feedback}))
                return

            # --- Always-correct Evaluation for creative challenges ---
            if challenge_type == "image_description":
                is_correct = True
                feedback = "Thank you for your creative description!"
                yield ProcessorPart(json.dumps({"is_correct": is_correct, "feedback": feedback}))
                return

            # --- LLM-based Evaluation for nuanced challenges (if any) ---
            # (Currently, all challenges are handled above, but this structure allows for future expansion)
            prompt_input = AnswerEvaluationInput(
                user_answer=user_answer,
                target_text=target_text,
                challenge_type=challenge_type,
            )
            
            formatted_prompt = self.prompt.format(**prompt_input)
            logger.info(f"--- GenAI-Processor REQUEST (LLM Eval) ---\\nPROMPT: {formatted_prompt}\\n")

            for model_name in self.model_names:
                try:
                    response = ""
                    model = genai_model.GenaiModel(model_name=model_name, api_key=self.api_key)
                    model_input_stream = streams.stream_content([ProcessorPart(formatted_prompt)])
                    async for part in model(model_input_stream):
                        if part.text:
                            response += part.text
                    
                    logger.info(f"--- GenAI-Processor RESPONSE (model: {model_name}) ---\\nRESPONSE: {response}\\n")
                    
                    cleaned_response = response.strip().replace("```json", "").replace("```", "")
                    response_data = json.loads(cleaned_response)
                    yield ProcessorPart(json.dumps(response_data))
                    return
                except Exception as e:
                    logger.error(f"Error evaluating answer with processor (model: {model_name}): {e}")
                    continue
            
            logger.error("All models failed. Falling back to simple string matching for correctness.")
            is_correct = self._clean_text(user_answer) == self._clean_text(target_text)
            feedback = "Correct!" if is_correct else f"Incorrect. The correct answer is: {target_text}"
            yield ProcessorPart(json.dumps({"is_correct": is_correct, "feedback": feedback, "fallback": True}))

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing input for evaluation: {e}")
            yield ProcessorPart(json.dumps({"error": "Invalid input format."}))

    async def evaluate_answer(
        self,
        user_answer: str,
        target_text: str,
        challenge_type: str
    ) -> dict:
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
            return json.loads(response_json)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response from evaluation chain.")
            return {"is_correct": False, "feedback": "Sorry, there was an error evaluating your answer."}