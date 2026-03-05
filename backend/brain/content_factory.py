"""
The Autonomous Content Factory
────────────────────────────────
A multi-platform syndication pipeline. Ingests raw text, audio transcripts, 
or chaotic notes and orchestrates the generation of polished, platform-native content.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any

from core.model_providers import GenerationResult
from agents.controller import AgentController
from agents.tools.doc_reader import DocumentReader

logger = logging.getLogger(__name__)

CONTENT_SYSTEM_PROMPT = """\
You are an Elite Media Syndicator and Copywriter.
Your job is to take raw, chaotic input text and spin it into 3 polished assets.

You MUST format your output EXACTLY as follows:

=== TWITTER_THREAD ===
<Write a highly engaging, native-feeling 5-10 part thread. Use emojis. No cringe hooks.>

=== LINKEDIN_POST ===
<Write a professional but story-driven post. Include a strong hook and line breaks.>

=== IMAGE_PROMPTS ===
<Write 3 highly detailed Midjourney/DALL-E prompts to create thumbnail art for this content.>
"""

class ContentFactory:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.reader = DocumentReader()
        
    def syndicate_content(self, file_path: str, output_dir: str = "syndicated_assets"):
        """Run the content generation pipeline."""
        logger.info(f"🏭 Content Factory spinning up for: {file_path}")
        
        doc_content = self.reader.read(file_path)
        if not doc_content:
            print(f"❌ Could not extract text from document: {file_path}")
            return
            
        print(f"🔄 Processing source material ({len(doc_content)} chars)...")

        prompt = f"==== RAW SOURCE TEXT ====\n{doc_content}\n=========================\n\n" \
                 f"Extract the core value from this messy source and generate the 3 required assets."

        result = self.agent.process(
            user_input=prompt,
            use_thinking_loop=False, # We want creative flow, not rigorous mathematical logic
            max_tool_calls=0,
            system_prompt_override=CONTENT_SYSTEM_PROMPT
        )
        
        if result.error:
            print(f"❌ Factory Pipeline Failed: {result.error}")
            return
            
        self._write_assets_to_disk(result.answer, output_dir, Path(file_path).stem)

    def _write_assets_to_disk(self, raw_output: str, output_dir: str, base_name: str):
        """Parse the generated text blocks and save them to neatly organized files."""
        out_path = Path(output_dir) / base_name
        out_path.mkdir(parents=True, exist_ok=True)
        
        # Simple string splitting based on our strict prompt format
        try:
            parts = raw_output.split("===")
            twitter = ""
            linkedin = ""
            images = ""
            
            for index, p in enumerate(parts):
                if "TWITTER_THREAD" in p and index + 1 < len(parts):
                    twitter = parts[index+1].strip()
                elif "LINKEDIN_POST" in p and index + 1 < len(parts):
                    linkedin = parts[index+1].strip()
                elif "IMAGE_PROMPTS" in p and index + 1 < len(parts):
                    images = parts[index+1].strip()

            if twitter:
                (out_path / "1_twitter_thread.txt").write_text(twitter, encoding='utf-8')
            if linkedin:
                (out_path / "2_linkedin_post.txt").write_text(linkedin, encoding='utf-8')
            if images:
                (out_path / "3_image_prompts.txt").write_text(images, encoding='utf-8')
                
            # Fallback if the AI messed up the formatting
            if not twitter and not linkedin:
                (out_path / "raw_generation.txt").write_text(raw_output, encoding='utf-8')
                print("⚠️ Formatting issue detected. Saved raw output instead.")
            else:
                print(f"✅ Syndication Complete! Assets saved to: {out_path.absolute()}")
                
        except Exception as e:
            logger.error(f"Failed to write assets: {e}")
            (out_path / "raw_generation.txt").write_text(raw_output, encoding='utf-8')
            print(f"⚠️ Saved raw output to: {out_path.absolute()}")
