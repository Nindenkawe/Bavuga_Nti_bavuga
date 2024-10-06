from fastapi import FastAPI, Request
from googletrans import Translator
import random

app = FastAPI()

WORDS = ["apple", "banana", "cat", "dog", ...]
print(WORDS)

@app.get("/")
async def home(request: Request):
    # Generate random English text (adjust length as needed)
    random_text = " ".join(random.choice(WORDS) for _ in range(50))

    # Translate to Kinyarwanda using Google Translate API
    translator = Translator()
    translated_text = translator.translate(random_text, dest="rw").text

    return {
        "random_text": random_text,
        "translated_text": translated_text,
    }

@app.post("/submit_answer")
async def submit_answer(request: Request):
    # Get user's answer from request body
    data = await request.json()
    user_answer = data.get("answer")

    # Check if answer is correct (implement your logic here)
    is_correct = check_answer(user_answer)

    # Update score (implement your logic here)
    update_score(is_correct)

    return {"is_correct": is_correct}

# Implement functions for checking answers and updating scores
def check_answer(user_answer):
    # Your logic to compare user_answer with correct answer
    pass

def update_score(is_correct):
    # Your logic to update the user's score
    pass