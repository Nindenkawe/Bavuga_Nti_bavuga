# /home/titeuf/Documents/Bavuga_Nti_bavuga-main/db_logic.py
import os
from dotenv import load_dotenv
import motor.motor_asyncio
from pydantic import BaseModel, Field
from typing import Optional, Any
from bson import ObjectId
import logging
import json
import asyncio

# --- Development Mode Configuration ---
DEV_MODE = False
DEV_DB_FILE = "dev_db.json"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "language_app") # Default name if not set

if not MONGODB_URI and not DEV_MODE:
    logger.error("MONGODB_URI not found in environment variables.")
    # raise ValueError("MONGODB_URI environment variable is required when not in development mode.")

# --- Database Client ---
client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None

def init_app_mode(dev_mode: bool):
    """Initializes the application mode (dev or production)."""
    global DEV_MODE
    DEV_MODE = dev_mode
    if DEV_MODE:
        logger.info("Application starting in DEVELOPMENT mode.")
        _init_dev_db()
    else:
        logger.info("Application starting in PRODUCTION mode.")

def _init_dev_db():
    """Initializes the development database if it doesn't exist."""
    if not os.path.exists(DEV_DB_FILE):
        with open(DEV_DB_FILE, "w") as f:
            json.dump({
                "challenges": [],
                "submissions": [],
                "game_state": [{
                    "_id": {"$oid": "60c72b9f9b1d8b3b4e8a0b1a"},
                    "state_name": "global",
                    "lives": 3,
                    "score": 0,
                    "incorrect_answers": [],
                    "pending_riddle": None,
                    "game_mode": "translation"
                }]
            }, f, indent=4)
        logger.info(f"Initialized development database at {DEV_DB_FILE}")

async def connect_to_mongo():
    """Connects to MongoDB."""
    if DEV_MODE:
        return
    global client, db
    logger.info("Connecting to MongoDB...")
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        await client.admin.command('ping')
        logger.info("Successfully connected to MongoDB.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        client = None
        db = None

async def close_mongo_connection():
    """Closes the MongoDB connection."""
    if DEV_MODE:
        return
    global client
    if client:
        logger.info("Closing MongoDB connection...")
        client.close()
        logger.info("MongoDB connection closed.")

def get_database() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Returns the database instance."""
    if DEV_MODE:
        raise RuntimeError("get_database() should not be called in development mode.")
    if db is None:
        logger.error("Database instance is not available. Connection might have failed.")
        raise RuntimeError("Database not initialized. Check MongoDB connection.")
    return db

# --- Pydantic Models for Database Documents ---
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, field):
        if isinstance(v, (str, ObjectId)):
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)
        raise TypeError('ObjectId required')


    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class Challenge(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    source_text: str
    target_text: str
    context: Optional[str] = None
    challenge_type: str
    difficulty: int

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class GameState(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    state_name: str = "global"
    lives: int = 3
    score: int = 0
    incorrect_answers: list[str] = []
    pending_riddle: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Submission(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    challenge_id: PyObjectId
    user_answer: Optional[str] = None
    image_analysis_result: Optional[str] = None
    is_correct: Optional[bool] = None
    score: int = 0
    submitted_at: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# --- Dev Mode Database Operations ---

def _read_dev_db():
    with open(DEV_DB_FILE, "r") as f:
        return json.load(f)

def _write_dev_db(data):
    with open(DEV_DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def save_challenge_dev(challenge_data: Challenge) -> ObjectId:
    await asyncio.sleep(0.01) # Simulate async
    db_data = _read_dev_db()
    challenge_dict = challenge_data.model_dump(by_alias=True, exclude_none=True)
    new_id = ObjectId()
    challenge_dict["_id"] = {"$oid": str(new_id)}
    db_data["challenges"].append(challenge_dict)
    _write_dev_db(db_data)
    logger.info(f"Saved challenge with ID: {new_id} in dev db")
    return new_id

async def get_challenge_dev(challenge_id: str) -> Optional[Challenge]:
    await asyncio.sleep(0.01) # Simulate async
    db_data = _read_dev_db()
    for challenge in db_data["challenges"]:
        if challenge["_id"]["$oid"] == challenge_id:
            # Pydantic model expects `_id` at the top level, not inside a dict
            challenge_data = challenge.copy()
            challenge_data["_id"] = challenge_data["_id"]["$oid"]
            return Challenge(**challenge_data)
    logger.warning(f"Challenge not found with ID: {challenge_id} in dev db")
    return None

async def save_submission_dev(submission_data: Submission) -> ObjectId:
    await asyncio.sleep(0.01) # Simulate async
    db_data = _read_dev_db()
    submission_dict = submission_data.model_dump(by_alias=True, exclude_none=True)
    new_id = ObjectId()
    submission_dict["_id"] = {"$oid": str(new_id)}
    from datetime import datetime
    submission_dict["submitted_at"] = datetime.utcnow().isoformat()
    # Ensure challenge_id is a string for JSON serialization
    submission_dict["challenge_id"] = str(submission_data.challenge_id)
    db_data["submissions"].append(submission_dict)
    _write_dev_db(db_data)
    logger.info(f"Saved submission with ID: {new_id} for challenge ID: {submission_data.challenge_id} in dev db")
    return new_id

async def get_total_score_dev() -> int:
    await asyncio.sleep(0.01) # Simulate async
    db_data = _read_dev_db()
    return sum(s.get("score", 0) for s in db_data["submissions"])

async def get_game_state_dev() -> GameState:
    await asyncio.sleep(0.01) # Simulate async
    db_data = _read_dev_db()
    state_data = db_data["game_state"][0]
    # Pydantic model expects `_id` at the top level, not inside a dict
    state_data_copy = state_data.copy()
    state_data_copy["_id"] = state_data_copy["_id"]["$oid"]
    return GameState(**state_data_copy)

async def update_game_state_dev(state: GameState):
    await asyncio.sleep(0.01) # Simulate async
    db_data = _read_dev_db()
    state_dict = state.model_dump(exclude={"id", "state_name"})
    # Update the global state in our JSON db
    db_data["game_state"][0].update(state_dict)
    _write_dev_db(db_data)
    logger.info(f"Updated game state in dev db: Lives={state.lives}, Score={state.score}")


# --- Unified Database Operations ---

async def save_challenge(challenge_data: Challenge) -> ObjectId:
    """Saves a new challenge to the database."""
    if DEV_MODE:
        return await save_challenge_dev(challenge_data)
    database = get_database()
    challenge_dict = challenge_data.model_dump(by_alias=True, exclude_none=True)
    result = await database["challenges"].insert_one(challenge_dict)
    logger.info(f"Saved challenge with ID: {result.inserted_id}")
    return result.inserted_id

async def get_challenge(challenge_id: str) -> Optional[Challenge]:
    """Retrieves a challenge by its ID."""
    if DEV_MODE:
        return await get_challenge_dev(challenge_id)
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
    if DEV_MODE:
        return await save_submission_dev(submission_data)
    database = get_database()
    if isinstance(submission_data.challenge_id, str):
         submission_data.challenge_id = PyObjectId(submission_data.challenge_id)
    submission_dict = submission_data.model_dump(by_alias=True, exclude_none=True)
    from datetime import datetime
    submission_dict["submitted_at"] = datetime.utcnow()
    result = await database["submissions"].insert_one(submission_dict)
    logger.info(f"Saved submission with ID: {result.inserted_id} for challenge ID: {submission_data.challenge_id}")
    return result.inserted_id

async def get_total_score() -> int:
    """Calculates the total score across all submissions."""
    if DEV_MODE:
        return await get_total_score_dev()
    database = get_database()
    pipeline = [
        {"$group": {"_id": None, "totalScore": {"$sum": "$score"}}}
    ]
    result = await database["submissions"].aggregate(pipeline).to_list(length=1)
    return result[0]["totalScore"] if result else 0

async def get_game_state() -> GameState:
    """Retrieves the current game state, creating it if it doesn't exist."""
    if DEV_MODE:
        return await get_game_state_dev()
    database = get_database()
    state_data = await database["game_state"].find_one({"state_name": "global"})
    if state_data:
        return GameState(**state_data)
    else:
        logger.info("No game state found, creating a default one.")
        default_state = GameState()
        await database["game_state"].insert_one(default_state.model_dump(by_alias=True, exclude_none=True))
        return default_state

async def update_game_state(state: GameState):
    """Updates the game state in the database."""
    if DEV_MODE:
        return await update_game_state_dev(state)
    database = get_database()
    await database["game_state"].update_one(
        {"state_name": "global"},
        {"$set": state.model_dump(exclude={"id", "state_name"})},
        upsert=True
    )
    logger.info(f"Updated game state: Lives={state.lives}, Score={state.score}")

async def get_recent_challenge_texts(limit: int = 20) -> list[str]:
    """Fetches the text of recent translation challenges to avoid repetition."""
    if DEV_MODE:
        # This is a simplified version for dev mode
        db_data = _read_dev_db()
        challenges = db_data.get("challenges", [])
        # Sort by a simulated timestamp or just take the last few
        challenges.sort(key=lambda x: x.get("_id", {}).get("$oid", ""), reverse=True)
        return [c["source_text"] for c in challenges[:limit] if "source_text" in c]

    database = get_database()
    challenges = database["challenges"].find(
        {"source_text": {"$ne": None}},
        {"source_text": 1, "_id": 0}
    ).sort("_id", -1).limit(limit)
    
    texts = await challenges.to_list(length=limit)
    return [item["source_text"] for item in texts]

async def get_challenge_feedback(challenge_id: str) -> list[dict]:
    """Retrieves feedback for a specific challenge."""
    if DEV_MODE:
        # Dev mode doesn't have feedback implemented yet
        return []
    database = get_database()
    feedback = database["feedback"].find({"challenge_id": ObjectId(challenge_id)})
    return await feedback.to_list(length=100)

async def get_all_user_answers_for_challenge(challenge_id: str) -> list[str]:
    """Retrieves all user answers for a specific challenge."""
    if DEV_MODE:
        db_data = _read_dev_db()
        answers = []
        for sub in db_data.get("submissions", []):
            if str(sub.get("challenge_id")) == challenge_id and sub.get("user_answer"):
                answers.append(sub["user_answer"])
        return answers

    database = get_database()
    submissions = database["submissions"].find(
        {"challenge_id": ObjectId(challenge_id)},
        {"user_answer": 1, "_id": 0}
    )
    answers = await submissions.to_list(length=None)
    return [item["user_answer"] for item in answers if item.get("user_answer")]

class Feedback(BaseModel):
    challenge_id: PyObjectId
    rating: int
    comment: Optional[str] = None

async def save_feedback(feedback_data: Feedback) -> ObjectId:
    """Saves user feedback to the database."""
    if DEV_MODE:
        # Dev mode doesn't have feedback implemented yet
        logger.info("Feedback saving is not implemented in dev mode.")
        return ObjectId()
    database = get_database()
    feedback_dict = feedback_data.model_dump(by_alias=True, exclude_none=True)
    result = await database["feedback"].insert_one(feedback_dict)
    return result.inserted_id