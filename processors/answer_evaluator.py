import asyncio
import logging
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

class AnswerEvaluatorProcessor:
    def __init__(self, model: Optional[genai.GenerativeModel]):
        self.model = model

    async def _evaluate_answer_dev(
        self, user_answer: str, target_text: str, challenge_type: str
    ) -> bool:
        await asyncio.sleep(0.05)
        return user_answer.lower() == target_text.lower()

    async def evaluate_answer(
        self, user_answer: str, target_text: str, challenge_type: str
    ) -> bool:
        """Evaluates a user's answer using the Gemini AI model."""
        if not self.model:
            return await self._evaluate_answer_dev(user_answer, target_text, challenge_type)

        try:
            # For riddles, the answer must be exact (or a known variation)
            if challenge_type == "gusakuza":
                # Use simple string comparison for riddles to enforce cultural accuracy
                return user_answer.lower().strip() == target_text.lower().strip()

            prompt = (
                f"You are an expert in Kinyarwanda and English. The target text is '{target_text}'. The user's answer is '{user_answer}'. "
                f"Is the user's answer a correct translation? Consider synonyms and minor grammatical variations. Respond ONLY with 'Correct' or 'Incorrect'."
            )
            
            logger.info(f"--- GEMINI API REQUEST ---\nPROMPT: {prompt}\n")
            response = await self.model.generate_content_async(prompt)
            logger.info(f"--- GEMINI API RESPONSE ---\nRESPONSE: {response.text}\n")

            # Stricter check for the word 'correct'
            return response.text.strip().lower() == 'correct'
        except Exception as e:
            logger.error(f"Error evaluating answer with agent: {e}")
            return await self._evaluate_answer_dev(user_answer, target_text, challenge_type)
