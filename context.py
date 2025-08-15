# context.py
from typing import Optional
from genai_processors.processor import Processor
from processors.challenge_generator import ChallengeGeneratorProcessor
from processors.answer_evaluator import AnswerEvaluatorProcessor

# Global AI Clients
challenge_generator: ChallengeGeneratorProcessor | None = None
answer_evaluator: AnswerEvaluatorProcessor | None = None
tts_processor: Processor | None = None
stt_processor: Processor | None = None
