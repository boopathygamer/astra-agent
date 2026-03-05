"""
Reverse-Engineering Code Transpiler
─────────────────────────────────────
Ingests messy legacy code, extracts raw business logic into an 
Intermediate Representation (IR), and generates modern code.
"""

import os
from pathlib import Path
import logging
from typing import Dict, List, Optional

from agents.controller import AgentController
from agents.profiles.migration_architect import MigrationArchitect

logger = logging.getLogger(__name__)


# Prompt used entirely to strip syntax and extract pure logic
ABSTRACTION_PROMPT = """\
You are an Abstract Syntax Transpiler.
Your job is to read the provided source code and DESTROY any reliance on its specific programming language.
You must extract the pure mathematical rules, state changes, API inputs/outputs, and business logic into an "Intermediate Representation" (IR).

DO NOT translate the code. Extract the meaning.
Write the output as a detailed English + Pseudocode specification.

==== SOURCE CODE ====
{source_code}
=====================
"""


class ReverseTranspiler:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.architect = MigrationArchitect(self.agent)

    def _discover_files(self, source_dir: str) -> List[Path]:
        """Phase 1: Ingestion. Find all relevant source files ignoring typical junk."""
        directory = Path(source_dir)
        if not directory.exists() or not directory.is_dir():
            logger.error(f"❌ Source directory '{source_dir}' not found.")
            return []

        ignore_dirs = {'.git', 'node_modules', 'venv', '__pycache__', 'target', 'build'}
        valid_extensions = {'.py', '.js', '.ts', '.java', '.php', '.cs', '.go', '.rb', '.cpp', '.c'}

        files_to_migrate = []
        for root, dirs, files in os.walk(directory):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                path = Path(root) / file
                if path.suffix in valid_extensions:
                    files_to_migrate.append(path)

        logger.info(f"📂 Found {len(files_to_migrate)} files in '{source_dir}' for migration.")
        return files_to_migrate

    def _extract_abstraction(self, file_path: Path) -> Optional[str]:
        """Phase 2: Abstraction. Convert legacy code to pure logic."""
        logger.info(f"🧠 Abstracting logic from: {file_path.name}")
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return None

        prompt = ABSTRACTION_PROMPT.format(source_code=content)
        
        # We don't need the thinking loop for abstraction, a single strong pass is usually enough.
        result = self.agent.process(user_input=prompt, use_thinking_loop=False, max_tool_calls=0)
        
        if result.error:
            logger.error(f"Abstraction failed for {file_path.name}: {result.error}")
            return None
            
        return result.answer

    def transpile_directory(self, source_dir: str, target_lang: str, output_dir: str = "transpiled_output"):
        """Main execution sequence."""
        print(f"\n🔄 Initializing Reverse Transpiler (Target: {target_lang})")
        print("=" * 60)
        
        files = self._discover_files(source_dir)
        if not files:
            print("No transpilable files found. Aborting.")
            return

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        successful = 0
        for file in files:
            print(f"\n[Processing] {file.name}...")
            
            # Phase 2: Extract IR
            abstract_logic = self._extract_abstraction(file)
            if not abstract_logic:
                continue
                
            # Phase 3: Architect Modern Code
            generation_result = self.architect.generate_modern_code(abstract_logic, target_lang)
            
            if generation_result.error:
                print(f"❌ Failed to generate {target_lang} code for {file.name}")
                continue

            # Strip possible markdown blocks from the raw code output
            code = generation_result.answer
            if code.startswith("```"):
                lines = code.split("\n")
                if len(lines) > 2:
                    code = "\n".join(lines[1:-1])

            # Save the new file
            lang_extensions = {"rust": ".rs", "python": ".py", "go": ".go", "typescript": ".ts", "javascript": ".js"}
            ext = lang_extensions.get(target_lang.lower(), ".txt")
            
            new_filename = f"{file.stem}_modern{ext}"
            new_file_path = out_path / new_filename
            
            try:
                new_file_path.write_text(code, encoding='utf-8')
                print(f"✅ Successfully transpiled -> {new_file_path}")
                successful += 1
            except Exception as e:
                print(f"❌ Failed to write output file: {e}")

        print("\n" + "=" * 60)
        print(f"🚀 Transpilation Complete! ({successful}/{len(files)} files migrated)")
        print(f"📁 Output Directory: {out_path.absolute()}")
        print("=" * 60 + "\n")
