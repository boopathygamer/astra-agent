"""
The 'Digital Estate' Archivist
────────────────────────────────
A specialized background worker that scans unorganized directories,
reads the contents of random files, figures out what they are,
and autonomously names/moves them into a pristine folder structure.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List

from core.model_providers import GenerationResult
from agents.controller import AgentController
from agents.tools.doc_reader import DocumentReader

logger = logging.getLogger(__name__)

ARCHIVIST_SYSTEM_PROMPT = """\
You are an Elite Digital Archivist and Librarian.
Your job is to read messy, raw text from unorganized files and categorize them perfectly.

You must reply with EXACTLY TWO lines of text. Nothing else.
Line 1: A clean, 1-3 word Category Name (e.g., "Tax Documents", "Memes", "Design Specs")
Line 2: A perfectly standardized, descriptive snake_case file name without extension (e.g., "2024_q1_tax_return")

==== FILE CONTENT ====
{file_content}
======================
"""

class DigitalArchivist:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.reader = DocumentReader()

    def organize_directory(self, target_dir: str):
        """Scan a chaotic folder and cleanly organize it."""
        path = Path(target_dir)
        if not path.exists() or not path.is_dir():
            print(f"❌ Target directory '{target_dir}' not found.")
            return

        print(f"\n📂 Digital Archivist deployed to: {target_dir}")
        print("Scanning files...")

        # Find files directly in the root of the target dir (don't dig recursively yet to avoid infinite loops)
        files = [f for f in path.iterdir() if f.is_file() and not f.name.startswith('.')]
        
        if not files:
            print("No files found to organize.")
            return

        organized_count = 0
        for file in files:
            print(f"  -> Reading {file.name}...")
            
            # Read snippet of file (first 3000 chars are usually enough to categorize)
            content = self.reader.read(str(file))
            if not content:
                print("     ⚠️ Could not read content. Skipping.")
                continue
            
            snippet = content[:3000]
            
            prompt = ARCHIVIST_SYSTEM_PROMPT.replace("{file_content}", snippet)
            
            # Use small fast model calls
            result = self.agent.process(
                user_input=prompt,
                use_thinking_loop=False,
                max_tool_calls=0,
                system_prompt_override=ARCHIVIST_SYSTEM_PROMPT
            )
            
            if result.error or not result.answer:
                print("     ❌ Failed to categorize.")
                continue
                
            lines = [line.strip() for line in result.answer.split('\n') if line.strip()]
            if len(lines) >= 2:
                category = lines[0].strip('`"*')
                new_base_name = lines[1].strip('`"*')
                
                # Create category folder
                category_dir = path / category
                category_dir.mkdir(exist_ok=True)
                
                # Move and rename
                new_path = category_dir / f"{new_base_name}{file.suffix}"
                
                # Ensure we don't overwrite
                counter = 1
                while new_path.exists():
                    new_path = category_dir / f"{new_base_name}_{counter}{file.suffix}"
                    counter += 1
                
                try:
                    shutil.move(str(file), str(new_path))
                    print(f"     ✅ Moved to: {category}/{new_path.name}")
                    organized_count += 1
                except Exception as e:
                    print(f"     ❌ Failed to move: {e}")
            else:
                print("     ⚠️ AI returned invalid format.")

        print(f"\n✨ Archive Complete! Organized {organized_count}/{len(files)} files.")
