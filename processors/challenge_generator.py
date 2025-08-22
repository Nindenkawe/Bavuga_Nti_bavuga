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

    story_chapter_text: str
    story_context: str
    challenge_type: str


class ChallengeGeneratorProcessor(processor.Processor):
    def __init__(self, model_names: list[str], image_dir: str = "static/sampleimg"):
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
            "instruction_generation": (
                "You are a creative assistant for a language learning game. Based on the following story chapter and challenge type, create a short, engaging instruction for the player. "
                "Story Chapter: '{story_context}'. Challenge Type: '{challenge_type}'. "
                "The instruction should feel like it's part of the story. "
                "Example for 'kin_to_eng': 'Amara's guide said the following. What do you think he meant in English?' "
                "Example for 'image_description': 'Inspired by her visit, Amara saw this scene. How would you describe it?' "
                "Output ONLY the instruction text."
            ),
            "story_translation": (
                "Based on this story chapter: '{story_chapter_text}', create a language challenge. "
                "It should be a phrase from the story to translate from English to Kinyarwanda. "
                "Output as 'English phrase|Kinyarwanda translation'. No other text."
            ),
            "kin_to_eng_proverb": (
                "Based on the following story context: '{story_context}', provide a {level} Kinyarwanda proverb that is thematically related to the story, and its English translation, separated by a pipe (|). "
                "Example: 'Akabando k'iminsi gacibwa kare|A walking stick for old age is prepared in advance'. No other text."
            ),
            "eng_to_kin_phrase": (
                "Based on the following story context: '{story_context}', provide a simple {level} English phrase that a tourist in Rwanda might use, and its Kinyarwanda translation, separated by a pipe (|). "
                "Example: 'Where is the bathroom?|Bwihereho ni he?'. No other text."
            ),
            "riddle_hint": (
                "You are a creative Kinyarwanda language tutor. Your goal is to help a user solve a riddle.\n"
                "The riddle is: '{riddle}'\n"
                "The answer to the riddle is: '{answer}'\n"
                "The current story context is: '{story_context}'\n\n"
                "Based on all this information, provide a short, one-sentence hint for the riddle. The hint should subtly reference the story's themes or vocabulary AND help the user guess the answer.\n"
                "Also provide the English translation of the riddle itself.\n"
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
            return {"challenge_type": "image_description", "source_text": f"/static/sampleimg/{random.choice(os.listdir(self.image_dir))}", "target_text": "A beautiful Rwandan landscape.", "context": "This is a fallback image challenge."}
        else:
            return {"challenge_type": "kin_to_eng_proverb", "source_text": "Akabando k'iminsi gacibwa kare", "target_text": "A walking stick for old age is prepared in advance", "context": "Translate this Kinyarwanda proverb to English."}

    async def _run_text_processor(self, processor_input: Dict[str, Any], prompt_key: str) -> str:
        prompt = self.prompts[prompt_key]
        log_prompt = prompt.format(**processor_input)
        logger.info(f"\n--- GenAI-Processor REQUEST ---\nPROMPT: {log_prompt}\n")

        for model_name in self.model_names:
            try:
                processor = genai_model.GenaiModel(model_name=model_name, api_key=self.api_key)
                response = ""
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

    async def generate_hint(self, riddle: str, answer: str, story_context: str) -> dict:
        try:
            processor_input = {"riddle": riddle, "answer": answer, "story_context": story_context}
            response_text = await self._run_text_processor(processor_input, "riddle_hint")
            
            if not response_text: return {"error": "Failed to generate hint."}
            parts = response_text.split("|")
            if len(parts) < 2: return {"error": "Invalid hint format from model."}
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
            # Note the change here: we now expect a dictionary with 'challenge' and 'state'
            result_data = await self._generate_challenge_logic(
                input_data["difficulty"], GameState(**input_data["state"]),
                input_data["game_mode"]
            )
            # We serialize the entire result dictionary
            yield ProcessorPart(json.dumps(result_data))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing input for challenge generation: {e}")
            yield ProcessorPart(json.dumps({"error": "Invalid input format."}))

    async def _generate_challenge_logic(self, difficulty: int, state: GameState, game_mode: str) -> dict:
        '''
        Generates a challenge and returns it along with the updated game state.
        This is the core of the chaining technique, ensuring context is maintained.
        '''
        challenge = {}
        try:
            level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(difficulty, "intermediate")
            
            # --- Story Generation and Context Persistence ---
            # If there's no story or the story is finished, create a new one.
            # This state change will be passed back to the API layer.
            if not state.story or state.story_chapter >= len(json.loads(state.story).get("chapters", [])):
                story_json_str = await self._run_text_processor({}, "story_creation")
                if not story_json_str:
                    challenge = await self._generate_static_challenge(game_mode)
                else:
                    try:
                        state.story = json.dumps(json.loads(story_json_str.strip().replace("```json", "").replace("```", "")))
                        state.story_chapter = 0
                    except json.JSONDecodeError:
                        challenge = await self._generate_static_challenge(game_mode)
            
            story_data = json.loads(state.story)
            story_context = story_data["chapters"][state.story_chapter]
            
            processor_input = ChallengeInput(
                difficulty=difficulty, game_mode=game_mode, level=level, 
                story_chapter_text=story_context, story_context=story_context, challenge_type=""
            )

            # --- Challenge Generation using Story Context ---
            if game_mode == "story":
                processor_input["challenge_type"] = "story_translation"
                response_text = await self._run_text_processor(processor_input, "story_translation")
                context = f"Chapter {state.story_chapter + 1}: {story_context}"
                state.story_chapter += 1 # This state change is now persisted
                parts = re.sub(r'#+\s*|\*+\s*', '', response_text).strip().split("|")
                if len(parts) < 2:
                    challenge = await self._generate_static_challenge(game_mode)
                else:
                    challenge = {
                        "challenge_type": processor_input["challenge_type"], "source_text": parts[0].strip(), 
                        "target_text": parts[1].strip(), "context": context
                    }
            elif game_mode == "sakwe":
                if not self.ibisakuzo_examples:
                    challenge = {"error_message": "Riddle database is empty."}
                else:
                    riddle_data = random.choice(self.ibisakuzo_examples)
                    challenge = {
                        "challenge_type": "gusakuza_init", "source_text": "Sakwe sakwe!", 
                        "target_text": f"{riddle_data['riddle']}|{riddle_data['answer']}", 
                        "context": "Reply with 'soma' to get the riddle."
                    }
            elif game_mode == "image":
                # ... (image generation logic remains the same, but now uses story_context)
                # This part is already using story_context correctly.
                image_files = [f for f in os.listdir(self.image_dir) if f.endswith((".png", ".jpg", ".jpeg"))]
                if not image_files:
                    challenge = {"error_message": f"No images found in {self.image_dir}."}
                else:
                    try:
                        img = Image.open(os.path.join(self.image_dir, random.choice(image_files)))
                        prompt_input = {"image": img, "story_context": story_context}
                        image_prompt = await self._run_text_processor(prompt_input, "image_prompt_generation")
                        if not image_prompt:
                            challenge = await self._generate_static_challenge(game_mode)
                        else:
                            image_models = [m for m in self.model_names if "imagen" in m]
                            generated_image_data = await self._run_image_generation_processor(image_prompt, image_models)
                            if not generated_image_data:
                                challenge = await self._generate_static_challenge(game_mode)
                            else:
                                gen_path = os.path.join("static", "generated", "generated_image.png")
                                os.makedirs(os.path.dirname(gen_path), exist_ok=True)
                                with open(gen_path, "wb") as f: f.write(generated_image_data)
                                
                                instruction = await self._run_text_processor(
                                    {"story_context": story_context, "challenge_type": "image_description"}, "instruction_generation"
                                )
                                challenge = {
                                    "challenge_type": "image_description", "source_text": "/" + gen_path,
                                    "target_text": "There is no correct answer for this challenge.", "context": instruction
                                }
                    except Exception as e:
                        logger.error(f"Failed to process image: {e}")
                        challenge = await self._generate_static_challenge(game_mode)
            else: # Translation
                processor_input["challenge_type"] = random.choice(["kin_to_eng_proverb", "eng_to_kin_phrase"])
                response_text = await self._run_text_processor(processor_input, processor_input["challenge_type"])
                context = await self._run_text_processor(processor_input, "instruction_generation")
                parts = re.sub(r'#+\s*|\*+\s*', '', response_text).strip().split("|")
                if len(parts) < 2:
                    challenge = await self._generate_static_challenge(game_mode)
                else:
                    challenge = {
                        "challenge_type": processor_input["challenge_type"], "source_text": parts[0].strip(), 
                        "target_text": parts[1].strip(), "context": context
                    }
        except Exception as e:
            logger.error(f"Error generating challenge: {e}", exc_info=True)
            challenge = await self._generate_static_challenge(game_mode)

        # --- Return both challenge and state ---
        return {
            "challenge": challenge,
            "state": json.loads(state.model_dump_json()) # Ensure state is JSON serializable
        }