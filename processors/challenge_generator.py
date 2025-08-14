import os
import json
import random
import asyncio
import re
import logging
from typing import Optional

import google.generativeai as genai
from PIL import Image

from db_logic import GameState

logger = logging.getLogger(__name__)

class ChallengeGeneratorProcessor:
    def __init__(self, model: Optional[genai.GenerativeModel], dev_mode: bool, image_dir: str = "sampleimg"):
        self.model = model
        self.dev_mode = dev_mode
        self.image_dir = image_dir
        self.ibisakuzo_examples = []
        try:
            with open("riddles.json", "r") as f:
                self.ibisakuzo_examples = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(
                f"Could not load riddles.json: {e}. Dev mode riddles will be static."
            )

    async def _generate_challenge_dev(
        self, difficulty: int, state: GameState, game_mode: str = "translation"
    ) -> dict:
        """Generates a static challenge for development mode."""
        await asyncio.sleep(0.05)  # Simulate async call

        challenge_type = game_mode  # Default to game_mode

        if game_mode == "sakwe":
            if self.ibisakuzo_examples:
                riddle_data = random.choice(self.ibisakuzo_examples)
                target_text = f"{riddle_data['riddle']}|{riddle_data['answer']}"
            else:
                target_text = "Igisakuzo|Some Answer"  # Fallback
            return {
                "challenge_type": "gusakuza_init",
                "source_text": "Sakwe sakwe!",
                "target_text": target_text,
                "context": "Reply with 'soma' to get the riddle.",
            }
        elif game_mode == "image":
            image_files = [f for f in os.listdir(self.image_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if not image_files:
                return {"error_message": f"No images found in {self.image_dir} directory."}
            
            random_image_name = random.choice(image_files)
            source_text = f"/{self.image_dir}/{random_image_name}"
            
            return {
                "challenge_type": "image_description",
                "source_text": source_text,
                "target_text": "A beautiful Rwandan landscape.",
                "context": "This is a development mode image challenge.",
            }
        elif game_mode == "story":
            story_paragraph = "The morning air was crisp and cool in the village of Nyarugenge. Children's laughter echoed as they chased a rolling hoop down the dirt path. In the distance, the lush green hills of Kigali were waking up, ready for a new day."
            return {
                "challenge_type": "story_translation",
                "source_text": "Children's laughter echoed.",
                "target_text": "Ibitwenge by'abana byumvikanye.",
                "context": story_paragraph,
            }
        else:  # translation
            dev_translations = [
                {
                    "challenge_type": "kin_to_eng_proverb",
                    "source_text": "Akabando k'iminsi gacibwa kare",
                    "target_text": "A walking stick for old age is prepared in advance",
                    "context": "Translate this Kinyarwanda proverb to English."
                },
                {
                    "challenge_type": "eng_to_kin_phrase",
                    "source_text": "Good morning",
                    "target_text": "Mwaramutse",
                    "context": "Translate this English phrase to Kinyarwanda."
                }
            ]
            return random.choice(dev_translations)

    async def generate_challenge(
        self, difficulty: int, state: GameState, game_mode: str = "translation"
    ) -> dict:
        """Generates a challenge using the Gemini AI model and thematic linking."""
        if self.dev_mode:
            return await self._generate_challenge_dev(difficulty, state, game_mode)

        try:
            level = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(
                difficulty, "intermediate"
            )
            challenge_type = ""
            prompt = ""
            context = None

            # --- Story Mode ---
            if game_mode == "story":
                if not state.story or state.story_chapter >= len(json.loads(state.story).get("chapters", [])):
                    story_prompt = "Write a short, engaging story for a language learning game. The story should be about a character exploring Rwanda. The story should be broken down into 3 chapters. Each chapter should introduce new vocabulary. The story should be in English. The output should be a JSON object with a 'title' and a list of 'chapters', where each chapter is a string. Do not add any other text, titles, or formatting."
                    logger.info(f"--- GEMINI API STORY GENERATION REQUEST ---\nPROMPT: {story_prompt}\n")
                    response = await self.model.generate_content_async(story_prompt)
                    logger.info(f"--- GEMINI API STORY GENERATION RESPONSE ---\nRESPONSE: {response.text}\n")
                    
                    cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
                    story_data = json.loads(cleaned_response)
                    state.story = json.dumps(story_data)
                    state.story_chapter = 0
                
                story_data = json.loads(state.story)
                chapter_text = story_data["chapters"][state.story_chapter]
                challenge_type = "story_translation"
                prompt = f"Based on this chapter of a story: '{chapter_text}', create a language challenge. The challenge should be a phrase from the story to translate from English to Kinyarwanda. The output should be in the format 'English phrase|Kinyarwanda translation'. Do not add any other text, titles, or formatting."
                
                context = f"Chapter {state.story_chapter + 1}: {chapter_text}"
                state.story_chapter += 1

            # --- Thematic Linking ---
            elif state.thematic_words:
                word = state.thematic_words.pop(0)
                challenge_type = "themed_translation"
                prompt = f"Provide a simple English phrase using the word '{word}' and its Kinyarwanda translation, separated by a pipe (|). Example: 'The honey is sweet|Uburyo ni buryoshye'. Do not add any other text, titles, or formatting."
            else:
                # --- Standard Challenge Generation ---
                if game_mode == "sakwe":
                    challenge_type = "gusakuza"
                elif game_mode == "image":
                    challenge_type = "image_description"
                else:  # translation is the default
                    challenge_type = random.choice(
                        ["kin_to_eng_proverb", "eng_to_kin_phrase"]
                    )

            # --- Challenge Specific Logic ---
            if challenge_type == "gusakuza":
                if not self.ibisakuzo_examples:
                    return {"error_message": "Riddle database is empty."}
                riddle_data = random.choice(self.ibisakuzo_examples)
                return {
                    "challenge_type": "gusakuza_init",
                    "source_text": "Sakwe sakwe!",
                    "target_text": f"{riddle_data['riddle']}|{riddle_data['answer']}",
                    "context": "Reply with 'soma' to get the riddle.",
                }

            if challenge_type == "image_description":
                image_files = [f for f in os.listdir(self.image_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
                if not image_files:
                    return {"error_message": f"No images found in the {self.image_dir} directory."}
                
                random_image_name = random.choice(image_files)
                image_path = os.path.join(self.image_dir, random_image_name)
                
                try:
                    img = Image.open(image_path)
                    prompt = [
                        "Describe this image of Rwanda in a single, descriptive sentence. Provide the description in both Kinyarwanda and English, separated by a pipe (|). Example: 'Umusozi w'u Rwanda|A Rwandan hill'. Do not add any other text, titles, or formatting.",
                        img,
                    ]
                    source_text = f"/{self.image_dir}/{random_image_name}"
                except Exception as e:
                    logger.error(f"Failed to open or process image {image_path}: {e}")
                    return await self._generate_challenge_dev(difficulty, state, game_mode)
            
            elif not prompt: # If prompt wasn't set by thematic link
                if challenge_type == "kin_to_eng_proverb":
                     prompt = f"Provide a {level} Kinyarwanda proverb and its English translation, separated by a pipe (|). Example: 'Akabando k'iminsi gacibwa kare|A walking stick for old age is prepared in advance'. Do not add any other text, titles, or formatting."
                elif challenge_type == "eng_to_kin_phrase":
                     prompt = f"Provide a simple {level} English phrase and its Kinyarwanda translation, separated by a pipe (|). Example: 'Good morning|Mwaramutse'. Do not add any other text, titles, or formatting."


            # --- Gemini API Call ---
            log_prompt = prompt
            if isinstance(prompt, list):
                log_prompt = f"{prompt[0]} [Image: {getattr(prompt[1], 'filename', 'PIL Image')}]"

            logger.info(
                "\n================================================================\n"
                "GEMINI API REQUEST\n"
                "----------------------------------------------------------------\n"
                "PROMPT:\n%s\n"
                "================================================================",
                log_prompt
            )
            try:
                response = await self.model.generate_content_async(prompt)
                logger.info(
                    "\n================================================================\n"
                    "GEMINI API RESPONSE\n"
                    "----------------------------------------------------------------\n"
                    "RESPONSE:\n%s\n"
                    "================================================================",
                    response.text
                )
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}. Falling back to dev mode.")
                return await self._generate_challenge_dev(difficulty, state, game_mode)
            
            # Clean up the response to remove potential markdown
            cleaned_response = re.sub(r'#+\s*|\*+\s*', '', response.text).strip()
            parts = cleaned_response.split("|")

            if len(parts) < 2:
                raise ValueError(f"Invalid response format from agent: {response.text}")

            if challenge_type == "image_description":
                return {
                    "challenge_type": challenge_type,
                    "source_text": source_text,
                    "target_text": f"Kinyarwanda: {parts[0].strip()} | English: {parts[1].strip()}",
                    "context": "Describe the image in either Kinyarwanda or English.",
                }
            else:  # Translation challenges
                return {
                    "challenge_type": challenge_type,
                    "source_text": parts[0].strip(),
                    "target_text": parts[1].strip(),
                    "context": context, # Context from story mode
                }

        except Exception as e:
            logger.error(f"Error generating challenge with agent: {e}")
            return await self._generate_challenge_dev(difficulty, state, game_mode)
