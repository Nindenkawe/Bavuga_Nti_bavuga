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
    story_context: str


class ChallengeGeneratorProcessor(processor.Processor):
    def __init__(self, model_names: list[str], image_dir: str = "sampleimg"):
        self.model_names = model_names
        self.image_dir = image_dir
        self.ibisakuzo_examples = self._load_riddles()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        self.api_key = api_key

        # --- Prompt Definitions ---
        self.prompts = {
            "story_creation": (
                "Write a short, engaging story for a language learning game about a tourist exploring a specific landmark or cultural site in Rwanda (e.g., Volcanoes National Park, Akagera National Park, a local market in Kigali). "
                "The story should be broken into 3 chapters. Each chapter should introduce new vocabulary related to tourism, nature, or local culture. "
                "Output a JSON object with a 'title' and a list of 'chapters' (strings). "
                "Do not add any other text, titles, or formatting."
            ),
            "story_translation": (
                "Based on this story chapter: '{story_chapter_text}', create a language challenge. "
                "It should be a phrase from the story to translate from English to Kinyarwanda. "
                "Output as 'English phrase|Kinyarwanda translation'. No other text."
            ),
            "themed_sentence": (
                "Provide a simple English phrase using the word '{thematic_word}'. "
                "Example: 'The honey is sweet'. No other text."
            ),
            "translate_to_kinyarwanda": (
                "Translate the following English phrase to Kinyarwanda: '{english_phrase}'. "
                "Only output the Kinyarwanda translation. No other text."
            ),
            "kin_to_eng_proverb": (
                "Based on the following story context: '{story_context}', provide a {level} Kinyarwanda proverb that is thematically related to the story, and its English translation, separated by a pipe (|). "
                "Example: 'Akabando k\'iminsi gacibwa kare|A walking stick for old age is prepared in advance'. No other text."
            ),
            "eng_to_kin_phrase": (
                "Based on the following story context: '{story_context}', provide a simple {level} English phrase that a tourist in Rwanda might use, and its Kinyarwanda translation, separated by a pipe (|). "
                "Example: 'Where is the bathroom?|Bwihereho ni he?'. No other text."
            ),
            "image_description": (
                "Describe this image of Rwanda in a single, descriptive sentence that a tourist might find interesting. "
                "Provide the description in both Kinyarwanda and English, separated by a pipe (|). The description should highlight a cultural or natural aspect of the image. "
                "Example: 'Umusozi w\u0027u Rwanda ufite ibyiza nyaburanga|A Rwandan hill with beautiful scenery'. No other text."
            ),
            "riddle_hint": (
                "The Kinyarwanda riddle is: '{riddle}'. "
                "Based on the following story context: '{story_context}', provide a short, one-sentence hint for this riddle that subtly references the story's themes or vocabulary. "
                "Also provide the English translation of the riddle itself. "
                "Output as 'Hint: [Your hint here]|Translation: [Your translation here]'. No other text."
            ),
            "image_prompt_generation": (
                "You are a creative AI assistant. Your task is to generate a concise (under 100 words) text prompt for an image generation model. "
                "The prompt should describe a new, unique, and visually interesting scene in Rwanda, inspired by the provided image and the following story context: '{story_context}'. "
                "Focus on the key elements: subject, setting, style, and mood."
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
            return {"challenge_type": "image_description", "source_text": f"/sampleimg/{random.choice(os.listdir(self.image_dir))}", "target_text": "A beautiful Rwandan landscape.", "context": "This is a fallback image challenge."}
        else:
            return {"challenge_type": "kin_to_eng_proverb", "source_text": "Akabando k\'iminsi gacibwa kare", "target_text": "A walking stick for old age is prepared in advance", "context": "Translate this Kinyarwanda proverb to English."}

    async def _run_text_processor(self, processor_input: Dict[str, Any], prompt_key: str) -> str:
        prompt = self.prompts[prompt_key]
        log_prompt = prompt.format(**processor_input)
        logger.info(f"\n--- GenAI-Processor REQUEST ---\nPROMPT: {log_prompt}\n")

        for model_name in self.model_names:
            try:
                processor = genai_model.GenaiModel(model_name=model_name, api_key=self.api_key)
                response = ""
                # Handle image input for the model
                parts = [ProcessorPart(log_prompt)]
                if "image" in processor_input:
                    parts.append(ProcessorPart(processor_input["image"]))
                
                input_stream = streams.stream_content(parts)
                async for part in processor(input_stream):
                    if part.text:
                        response += part.text
                logger.info(f"\n--- GenAI-Processor RESPONSE (model: {model_name}) ---\nRESPONSE: {response}\n")
                return response
            except Exception as e:
                logger.warning(f"GenAI Processor call failed for model {model_name}: {e}")
                continue
        
        logger.error("All models failed.")
        return ""

    async def _run_image_generation_processor(self, prompt: str, image_models: list[str]) -> bytes:
        for model_name in image_models:
            try:
                processor = genai_model.GenaiModel(model_name=model_name, api_key=self.api_key)
                input_stream = streams.stream_content([ProcessorPart(prompt)])
                async for part in processor(input_stream):
                    if part.image:
                        return part.image
            except Exception as e:
                logger.warning(f"Image generation failed for model {model_name}: {e}")
                continue
        return None

    async def generate_hint(self, riddle: str, story_context: str) -> dict:
        """Generates a hint for a given riddle."""
        try:
            processor_input = {"riddle": riddle, "story_context": story_context}
            response_text = await self._run_text_processor(processor_input, "riddle_hint")
            
            if not response_text:
                return {"error": "Failed to generate hint."}

            parts = response_text.split("|")
            if len(parts) < 2:
                return {"error": "Invalid hint format from model."}

            hint = parts[0].replace("Hint:", "").strip()
            translation = parts[1].replace("Translation:", "").strip()

            return {"hint": hint, "translation": translation}

        except Exception as e:
            logger.error(f"Error generating hint: {e}", exc_info=True)
            return {"error": "An unexpected error occurred while generating the hint."}

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
            yield ProcessorPart(json.dumps(challenge_data))

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing input for challenge generation: {e}")
            yield ProcessorPart(json.dumps({"error": "Invalid input format."}))

    async def _generate_challenge_logic(self, difficulty: int, state: GameState, game_mode: str) -> dict:
        try:
            level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(difficulty, "intermediate")
            context = None
            
            # --- Story Generation: The Foundation ---
            if not state.story or state.story_chapter >= len(json.loads(state.story).get("chapters", [])):
                story_json_str = await self._run_text_processor({}, "story_creation")
                if not story_json_str:
                    logger.error("Failed to generate a story. Falling back.")
                    return await self._generate_static_challenge(game_mode)
                try:
                    story_data = json.loads(story_json_str.strip().replace("```json", "").replace("```", ""))
                except json.JSONDecodeError:
                    logger.error("Failed to decode story data from model. Falling back.")
                    return await self._generate_static_challenge(game_mode)
                state.story = json.dumps(story_data)
                state.story_chapter = 0
            
            story_data = json.loads(state.story)
            story_context = story_data["chapters"][state.story_chapter]
            processor_input = ChallengeInput(difficulty=difficulty, game_mode=game_mode, level=level, thematic_word="", story_chapter_text=story_context, story_context=story_context)

            # --- Game Mode Logic ---
            if game_mode == "story":
                response_text = await self._run_text_processor(processor_input, "story_translation")
                context = f"Chapter {state.story_chapter + 1}: {story_context}"
                state.story_chapter += 1
                challenge_type = "story_translation"

            elif game_mode == "sakwe":
                if not self.ibisakuzo_examples:
                    return {"error_message": "Riddle database is empty."}
                riddle_data = random.choice(self.ibisakuzo_examples)
                return {
                    "challenge_type": "gusakuza_init",
                    "source_text": "Sakwe sakwe!",
                    "target_text": f"{riddle_data['riddle']}|{riddle_data['answer']}",
                    "context": "Reply with 'soma' to get the riddle.",
                }

            elif game_mode == "image":
                image_files = [f for f in os.listdir(self.image_dir) if f.endswith((".png", ".jpg", ".jpeg"))]
                if not image_files: return {"error_message": f"No images found in {self.image_dir}."}
                
                random_image_name = random.choice(image_files)
                image_path = os.path.join(self.image_dir, random_image_name)
                
                try:
                    img = Image.open(image_path)
                    
                    prompt_generation_input = {"image": img, "story_context": story_context}
                    image_prompt = await self._run_text_processor(prompt_generation_input, "image_prompt_generation")

                    if not image_prompt:
                        logger.error("Failed to generate an image prompt. Falling back.")
                        return await self._generate_static_challenge(game_mode)

                    image_models = [m for m in self.model_names if "imagen" in m]
                    generated_image_data = await self._run_image_generation_processor(image_prompt, image_models)

                    if not generated_image_data:
                        logger.error("Failed to generate a new image. Falling back.")
                        return await self._generate_static_challenge(game_mode)

                    generated_image_path = os.path.join("static", "generated", "generated_image.png")
                    os.makedirs(os.path.dirname(generated_image_path), exist_ok=True)
                    with open(generated_image_path, "wb") as f:
                        f.write(generated_image_data)

                    return {
                        "challenge_type": "image_description",
                        "source_text": "/" + generated_image_path,
                        "target_text": "There is no correct answer for this challenge.",
                        "context": "Describe what you see in the generated image.",
                    }
                except Exception as e:
                    logger.error(f"Failed to process image {image_path}: {e}")
                    return await self._generate_static_challenge(game_mode)
            
            else: # Translation
                challenge_type = random.choice(["kin_to_eng_proverb", "eng_to_kin_phrase"])
                response_text = await self._run_text_processor(processor_input, challenge_type)

            # --- Process Response ---
            cleaned_response = re.sub(r'#+\s*|\*+\s*', '', response_text).strip()
            parts = cleaned_response.split("|")

            if len(parts) < 2:
                logger.error(f"Invalid response format: {response_text}. Falling back.")
                return await self._generate_static_challenge(game_mode)

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
        input_stream = streams.stream_content([ProcessorPart(input_json)])
        async for part in self(input_stream):
            if part.text:
                response_json += part.text
        
        try:
            return json.loads(response_json)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response from challenge generation chain.")
            return await self._generate_static_challenge(game_mode)
