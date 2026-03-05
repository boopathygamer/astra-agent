"""
Digital Twin Persona Ingestion
────────────────────────────────
Scans the user's workspace to learn their exact coding style,
variable naming conventions, and architectural preferences,
then persists this "Twin" into the memory store.
"""

import os
import ast
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

from brain.memory import MemoryManager

logger = logging.getLogger(__name__)

@dataclass
class CodingStyleProfile:
    indentation: int = 4
    uses_type_hints: bool = False
    docstring_style: str = "unknown"
    snake_case_vars: float = 0.0 # Percentage
    camel_case_vars: float = 0.0
    preferred_frameworks: list = None
    average_function_length: int = 0
    common_imports: list = None
    
    def __post_init__(self):
        if self.preferred_frameworks is None:
            self.preferred_frameworks = []
        if self.common_imports is None:
            self.common_imports = []

class TwinAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.variables = []
        self.imports = []
        self.has_type_hints = False

    def visit_FunctionDef(self, node):
        self.functions.append(node)
        if node.returns or any(arg.annotation for arg in node.args.args):
            self.has_type_hints = True
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables.append(target.id)
        self.generic_visit(node)
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name.split('.')[0])
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module.split('.')[0])
        self.generic_visit(node)


class DigitalTwinIngester:
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        
    def scan_workspace(self, directory: str) -> CodingStyleProfile:
        """Scan a directory and build a coding profile."""
        logger.info(f"🔍 Scanning workspace '{directory}' to build Digital Twin...")
        
        path = Path(directory)
        if not path.exists():
            logger.error(f"Directory {directory} does not exist.")
            return CodingStyleProfile()
            
        py_files = list(path.rglob("*.py"))
        if not py_files:
            logger.warning("No python files found to analyze.")
            return CodingStyleProfile()
            
        total_functions = 0
        total_function_lines = 0
        all_variables = []
        all_imports = set()
        uses_type_hints = False
        
        for file in py_files[:50]: # Cap at 50 to avoid massive memory usage
            try:
                content = file.read_text(encoding='utf-8')
                tree = ast.parse(content)
                analyzer = TwinAnalyzer()
                analyzer.visit(tree)
                
                # Metrics
                if analyzer.has_type_hints:
                    uses_type_hints = True
                    
                for func in analyzer.functions:
                    total_functions += 1
                    func_len = getattr(func, 'end_lineno', func.lineno) - func.lineno
                    total_function_lines += func_len
                    
                all_variables.extend(analyzer.variables)
                all_imports.update(analyzer.imports)
                
            except Exception as e:
                logger.debug(f"Could not parse {file.name}: {e}")
                
        # Analyze variables
        snake_case = sum(1 for v in all_variables if '_' in v and v.islower())
        camel_case = sum(1 for v in all_variables if any(c.isupper() for c in v))
        total_vars = len(all_variables) or 1
        
        profile = CodingStyleProfile(
            uses_type_hints=uses_type_hints,
            snake_case_vars=(snake_case / total_vars) * 100,
            camel_case_vars=(camel_case / total_vars) * 100,
            average_function_length=int(total_function_lines / total_functions) if total_functions else 0,
            common_imports=list(all_imports)[:20]
        )
        
        # Save to memory store as the 'TwinProfile'
        self._persist_profile(profile)
        logger.info("✅ Digital Twin Profile generated and saved to memory!")
        return profile
        
    def _persist_profile(self, profile: CodingStyleProfile):
        """Save the profile directly into ChromaDB via MemoryManager."""
        doc = f"SYSTEM_TWIN_PROFILE: User writes code with avg function length {profile.average_function_length}. " \
              f"Type hints: {profile.uses_type_hints}. " \
              f"Snake case preference: {profile.snake_case_vars:.1f}%. " \
              f"Common libraries: {', '.join(profile.common_imports)}."
        
        # We store it with metadata so it can be specifically retrieved
        self.memory.collection.add(
            documents=[doc],
            metadatas=[{"type": "digital_twin", "schema": json.dumps(asdict(profile))}],
            ids=["twin_profile_001"]
        )

    def load_twin_prompt(self) -> str:
        """Retrieve the latest twin profile to inject into generation prompts."""
        results = self.memory.collection.get(
            ids=["twin_profile_001"]
        )
        if results and results.get("documents"):
            doc = results["documents"][0]
            return f"\n[DIGITAL TWIN OVERRIDE]: You MUST adopt this exact coding style: {doc}"
        return ""
