import os
import json
import random
import re
import logging
from typing import TypedDict, Any, Dict, AsyncIterator

from PIL import Image
from genai_processors import processor
from genai_processors.core import genai_model
from genai_processors import streams
from genai_processors.content_api import ProcessorPart

from db_logic import GameState

logger = logging.getLogger(__name__)


class ChallengeInput(TypedDict):
    difficulty: int
    game_mode: str
    level: str
    thematic_word: str
    story_chapter_text: str


class ChallengeGeneratorProcessor(processor.Processor):
    def __init__(self, model_name: str, image_dir: str = "sampleimg"):
        self.model_name = model_name
        self.image_dir = image_dir
        self.ibisakuzo_examples = self._load_riddles()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        self.api_key = api_key

        # --- Prompt Definitions ---
        self.prompts = {
            "story_creation": (
                "Write a short, engaging story for a language learning game about exploring Rwanda. "
                "Break the story into 3 chapters. Each chapter should introduce new vocabulary. "
                "Output a JSON object with a 'title' and a list of 'chapters' (strings). "
                "Do not add any other text, titles, or formatting."
            ),
            "story_translation": (
                "Based on this story chapter: '{{story_chapter_text}}', create a language challenge. "
                "It should be a phrase from the story to translate from English to Kinyarwanda. "
                "Output as 'English phrase|Kinyarwanda translation'. No other text."
            ),
            "themed_sentence": (
                "Provide a simple English phrase using the word '{{thematic_word}}'. "
                "Example: 'The honey is sweet'. No other text."
            ),
            "translate_to_kinyarwanda": (
                "Translate the following English phrase to Kinyarwanda: '{{english_phrase}}'. "
                "Only output the Kinyarwanda translation. No other text."
            ),
            "kin_to_eng_proverb": (
                "Provide a {{level}} Kinyarwanda proverb and its English translation, separated by a pipe (|). "
                "Example: 'Akabando k\'iminsi gacibwa kare|A walking stick for old age is prepared in advance'. No other text."
            ),
            "eng_to_kin_phrase": (
                "Provide a simple {{level}} English phrase and its Kinyarwanda translation, separated by a pipe (|). "
                "Example: 'Good morning|Mwaramutse'. No other text."
            ),
            "image_description": (
                "Describe this image of Rwanda in a single, descriptive sentence. "
                "Provide the description in both Kinyarwanda and English, separated by a pipe (|). "
                "Example: 'Umusozi w'u Rwanda|A Rwandan hill'. No other text."
            ),
        }

    def _load_riddles(self) -> list:
        try:
            with open("riddles.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load riddles.json: {e}. Riddles will be unavailable.")
            return []

    async def _generate_static_challenge(self, game_mode: str) -> dict:
        logger.info(f"Generating static fallback challenge for game_mode: {game_mode}")
        if game_mode == "sakwe":
            return {"challenge_type": "gusakuza_init", "source_text": "Sakwe sakwe!", "target_text": "Igisakuzo|Some Answer", "context": "Reply with 'soma' to get the riddle."}
        elif game_mode == "image":
            return {"challenge_type": "image_description", "source_text": "/sampleimg/Rw1.jpg", "target_text": "A beautiful Rwandan landscape.", "context": "This is a fallback image challenge."}
        else:
            return {"challenge_type": "kin_to_eng_proverb", "source_text": "Akabando k\'iminsi gacibwa kare", "target_text": "A walking stick for old age is prepared in advance", "context": "Translate this Kinyarwanda proverb to English."}

    async def _run_processor(self, processor_input: Dict[str, Any], prompt_key: str) -> str:
        prompt = self.prompts[prompt_key]
        processor = genai_model.GenaiModel(model_name=self.model_name, api_key=self.api_key)
        log_prompt = prompt.format(**processor_input)
        
        logger.info(f"\n--- GenAI-Processor REQUEST ---\nPROMPT: {log_prompt}\n")
        try:
            response = ""
            # Handle image input for the model
            parts = [ProcessorPart(text=log_prompt)]
            if "image" in processor_input:
                parts.append(ProcessorPart(image=processor_input["image"]))
            
            input_stream = streams.stream_content(parts)
            async for part in processor(input_stream):
                if part.text:
                    response += part.text
            logger.info(f"\n--- GenAI-Processor RESPONSE ---\nRESPONSE: {response}\n")
            return response
        except Exception as e:
            logger.error(f"GenAI Processor call failed: {e}")
            return ""

    async def call(self, input_stream: streams.AsyncIterable[ProcessorPart]) -> streams.AsyncIterable[ProcessorPart]:
        input_json = ""
        async for part in input_stream:
            if part.text:
                input_json += part.text
        
        try:
            input_data = json.loads(input_json)
            difficulty = input_data["difficulty"]
            state_dict = input_data["state"]
            state = GameState(**state_dict)
            game_mode = input_data["game_mode"]

            challenge_data = await self._generate_challenge_logic(difficulty, state, game_mode)
            yield ProcessorPart(text=json.dumps(challenge_data))

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing input for challenge generation: {e}")
            yield ProcessorPart(text=json.dumps({"error": "Invalid input format."}))

    async def _generate_challenge_logic(self, difficulty: int, state: GameState, game_mode: str) -> dict:
        try:
            level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(difficulty, "intermediate")
            context = None
            processor_input = ChallengeInput(difficulty=difficulty, game_mode=game_mode, level=level, thematic_word="", story_chapter_text="")

            # --- Story Mode ---
            if game_mode == "story":
                if not state.story or state.story_chapter >= len(json.loads(state.story).get("chapters", [])):
                    story_json_str = await self._run_processor({}, "story_creation")
                    story_data = json.loads(story_json_str.strip().replace("```json", "").replace("```", ""))
                    state.story = json.dumps(story_data)
                    state.story_chapter = 0
                
                story_data = json.loads(state.story)
                chapter_text = story_data["chapters"][state.story_chapter]
                processor_input["story_chapter_text"] = chapter_text
                response_text = await self._run_processor(processor_input, "story_translation")
                context = f"Chapter {state.story_chapter + 1}: {chapter_text}"
                state.story_chapter += 1
                challenge_type = "story_translation"

            # --- Thematic Linking ---
            elif state.thematic_words:
                word = state.thematic_words.pop(0)
                processor_input["thematic_word"] = word
                english_phrase = await self._run_processor(processor_input, "themed_sentence")
                
                if not english_phrase:
                    logger.error("Failed to generate a themed sentence. Falling back.")
                    return await self._generate_static_challenge(game_mode)

                translation_input = {"english_phrase": english_phrase}
                kinyarwanda_translation = await self._run_processor(translation_input, "translate_to_kinyarwanda")

                if not kinyarwanda_translation:
                    logger.error("Failed to translate the themed sentence. Falling back.")
                    return await self._generate_static_challenge(game_mode)
                
                response_text = f"{english_phrase}|{kinyarwanda_translation}"
                challenge_type = "themed_translation"

            # --- Standard Challenge Generation ---
            else:
                if game_mode == "sakwe":
                    if not self.ibisakuzo_examples: return {"error_message": "Riddle database is empty."}
                    riddle_data = random.choice(self.ibisakuzo_examples)
                    return {"challenge_type": "gusakuza_init", "source_text": "Sakwe sakwe!", "target_text": f"{riddle_data['riddle']}|{riddle_data['answer']}", "context": "Reply with 'soma' to get the riddle."}

                elif game_mode == "image":
                    image_files = [f for f in os.listdir(self.image_dir) if f.endswith((".png", ".jpg", ".jpeg"))]
                    if not image_files: return {"error_message": f"No images found in {self.image_dir}."}
                    
                    random_image_name = random.choice(image_files)
                    image_path = os.path.join(self.image_dir, random_image_name)
                    
                    try:
                        img = Image.open(image_path)
                        processor_input["image"] = img
                        response_text = await self._run_processor(processor_input, "image_description")
                        source_text = f"/{self.image_dir}/{random_image_name}"
                        challenge_type = "image_description"
                    except Exception as e:
                        logger.error(f"Failed to process image {image_path}: {e}")
                        return await self._generate_static_challenge(game_mode)
                
                else: # Translation
                    challenge_type = random.choice(["kin_to_eng_proverb", "eng_to_kin_phrase"])
                    response_text = await self._run_processor(processor_input, challenge_type)

            # --- Process Response ---
            cleaned_response = re.sub(r'#+\s*|\*+\s*', '', response_text).strip()
            parts = cleaned_response.split("|")

            if len(parts) < 2:
                logger.error(f"Invalid response format: {response_text}. Falling back.")
                return await self._generate_static_challenge(game_mode)

            if challenge_type == "image_description":
                return {"challenge_type": challenge_type, "source_text": source_text, "target_text": f"Kinyarwanda: {parts[0].strip()} | English: {parts[1].strip()}", "context": "Describe the image in either Kinyarwanda or English."}
            else:
                return {"challenge_type": challenge_type, "source_text": parts[0].strip(), "target_text": parts[1].strip(), "context": context}

        except Exception as e:
            logger.error(f"Error generating challenge: {e}", exc_info=True)
            return await self._generate_static_challenge(game_mode)

    async def generate_challenge(self, difficulty: int, state: GameState, game_mode: str) -> dict:
        """
        Generates a challenge. Convenience wrapper around the processor chain.
        """
        input_data = {
            "difficulty": difficulty,
            "state": state.dict(),
            "game_mode": game_mode,
        }
        input_json = json.dumps(input_data)
        
        response_json = ""
        input_stream = streams.stream_content([ProcessorPart(text=input_json)])
        async for part in self(input_stream):
            if part.text:
                response_json += part.text
        
        try:
            return json.loads(response_json)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response from challenge generation chain.")
            return await self._generate_static_challenge(game_mode)

