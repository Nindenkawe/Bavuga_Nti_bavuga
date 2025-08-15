from pydantic import BaseModel

class ChallengeResponse(BaseModel):
    challenge_id: str
    source_text: str
    context: str | None = None
    challenge_type: str
    error_message: str | None = None

class SubmissionResponse(BaseModel):
    message: str
    is_correct: bool
    correct_answer: str | None = None
    score_awarded: int
    new_total_score: int
    lives: int
    score: int

class TranscribeResponse(BaseModel):
    transcript: str
