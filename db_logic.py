# /home/titeuf/Documents/Bavuga_Nti_bavuga-main/db_logic.py
import os
from dotenv import load_dotenv
import motor.motor_asyncio
from pydantic import BaseModel, Field
from typing import Optional, Any
from bson import ObjectId
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "language_app") # Default name if not set

if not MONGODB_URI:
    logger.error("MONGODB_URI not found in environment variables.")
    # Handle the error appropriately, maybe raise an exception or exit
    # For now, we'll allow it to proceed but Motor will likely fail
    # raise ValueError("MONGODB_URI environment variable is required.")


# --- Database Client ---
# Use a single client instance managed by FastAPI lifespan events
client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None

async def connect_to_mongo():
    """Connects to MongoDB."""
    global client, db
    logger.info("Connecting to MongoDB...")
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        # Ping the server to check connection
        await client.admin.command('ping')
        logger.info("Successfully connected to MongoDB.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        client = None
        db = None
        # Depending on your error handling strategy, you might want to raise the exception
        # raise e

async def close_mongo_connection():
    """Closes the MongoDB connection."""
    global client
    if client:
        logger.info("Closing MongoDB connection...")
        client.close()
        logger.info("MongoDB connection closed.")

def get_database() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Returns the database instance."""
    if db is None:
        # This should ideally not happen if connect_to_mongo was successful
        logger.error("Database instance is not available. Connection might have failed.")
        raise RuntimeError("Database not initialized. Check MongoDB connection.")
    return db

# --- Pydantic Models for Database Documents ---
# Helps with data validation and structure

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, field):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class Challenge(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    source_text: str
    target_text: str
    context: Optional[str] = None
    challenge_type: str # e.g., "kin_to_eng_proverb", "eng_to_kin_phrase"
    difficulty: int

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Submission(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    challenge_id: PyObjectId
    user_answer: Optional[str] = None
    image_analysis_result: Optional[str] = None # Store AI's analysis of the image
    is_correct: Optional[bool] = None
    score: int = 0 # Score awarded for this submission (e.g., 1 for correct, 0 otherwise)
    submitted_at: Optional[Any] = None # Consider using datetime

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# --- Database Operations ---

async def save_challenge(challenge_data: Challenge) -> ObjectId:
    """Saves a new challenge to the database."""
    database = get_database()
    challenge_dict = challenge_data.model_dump(by_alias=True, exclude_none=True)
    result = await database["challenges"].insert_one(challenge_dict)
    logger.info(f"Saved challenge with ID: {result.inserted_id}")
    return result.inserted_id

async def get_challenge(challenge_id: str) -> Optional[Challenge]:
    """Retrieves a challenge by its ID."""
    database = get_database()
    try:
        obj_id = ObjectId(challenge_id)
    except Exception:
        logger.error(f"Invalid challenge ID format: {challenge_id}")
        return None
    challenge_data = await database["challenges"].find_one({"_id": obj_id})
    if challenge_data:
        return Challenge(**challenge_data)
    logger.warning(f"Challenge not found with ID: {challenge_id}")
    return None

async def save_submission(submission_data: Submission) -> ObjectId:
    """Saves a user's submission to the database."""
    database = get_database()
    # Ensure challenge_id is an ObjectId if it's passed as a string
    if isinstance(submission_data.challenge_id, str):
         submission_data.challenge_id = PyObjectId(submission_data.challenge_id)

    submission_dict = submission_data.model_dump(by_alias=True, exclude_none=True)
    # Add timestamp
    from datetime import datetime
    submission_dict["submitted_at"] = datetime.utcnow()

    result = await database["submissions"].insert_one(submission_dict)
    logger.info(f"Saved submission with ID: {result.inserted_id} for challenge ID: {submission_data.challenge_id}")
    return result.inserted_id

async def get_total_score() -> int:
    """Calculates the total score across all submissions."""
    database = get_database()
    # Sum the 'score' field from all documents in the submissions collection
    pipeline = [
        {"$group": {"_id": None, "totalScore": {"$sum": "$score"}}}
    ]
    result = await database["submissions"].aggregate(pipeline).to_list(length=1)
    return result[0]["totalScore"] if result else 0

async def get_recent_challenge_texts(limit: int = 20) -> list[str]:
    """Fetches the text of recent translation challenges to avoid repetition."""
    database = get_database()
    challenges = database["challenges"].find(
        {"original_text": {"$ne": None}},
        {"original_text": 1, "_id": 0}
    ).sort("timestamp", -1).limit(limit)
    
    texts = await challenges.to_list(length=limit)
    return [item["original_text"] for item in texts]

async def get_challenge_feedback(challenge_id: str) -> list[dict]:
    """Retrieves feedback for a specific challenge."""
    database = get_database()
    feedback = database["feedback"].find({"challenge_id": ObjectId(challenge_id)})
    return await feedback.to_list(length=100)

async def get_all_user_answers_for_challenge(challenge_id: str) -> list[str]:
    """Retrieves all user answers for a specific challenge."""
    database = get_database()
    submissions = database["submissions"].find(
        {"challenge_id": ObjectId(challenge_id)},
        {"user_answer": 1, "_id": 0}
    )
    answers = await submissions.to_list(length=None)
    return [item["user_answer"] for item in answers if item.get("user_answer")]

class Feedback(BaseModel):
    challenge_id: PyObjectId
    rating: int # e.g., 1-5 stars
    comment: Optional[str] = None

async def save_feedback(feedback_data: Feedback) -> ObjectId:
    """Saves user feedback to the database."""
    database = get_database()
    feedback_dict = feedback_data.model_dump(by_alias=True, exclude_none=True)
    result = await database["feedback"].insert_one(feedback_dict)
    return result.inserted_id

# Example of user-specific score (if you add user identification later)
# async def get_user_score(user_id: str) -> int:
#     database = get_database()
#     pipeline = [
#         {"$match": {"user_id": user_id}}, # Assuming you add user_id to Submission model
#         {"$group": {"_id": "$user_id", "totalScore": {"$sum": "$score"}}}
#     ]
#     result = await database["submissions"].aggregate(pipeline).to_list(length=1)
#     return result[0]["totalScore"] if result else 0
