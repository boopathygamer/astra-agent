"""
DevOps & PR Reviewer Profile
────────────────────────────
A specialized persona that acts as an autonomous DevOps Engineer.
Capable of reviewing codebases, formulating fixes for issues, 
and proposing Git patches/PRs.
"""

import logging
import subprocess # nosec B404
import os
from core.model_providers import GenerationResult
from agents.controller import AgentController

logger = logging.getLogger(__name__)

DEVOPS_PROMPT = """
You are the SENIOR DEVOPS ENGINEER and PR REVIEWER.
Your job is to read an issue description and a target codebase, and formulate a perfect code fix.
You act autonomously. 
When providing the fix, provide the exact `git diff` format or the exact bash commands 
(e.g., `git apply` or `patch`) required to implement the fix.

Focus on:
1. Writing clean, idiomatic code.
2. Avoiding breaking changes.
3. Ensuring the code integrates seamlessly with the existing architecture.
"""

class DevOpsReviewer:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller

    def autonomous_fix(self, issue: str, repo_path: str = ".") -> GenerationResult:
        """Analyze a repository and propose a fix for an issue."""
        logger.info(f"🛠️ DevOps Reviewer analyzing issue in {repo_path}")
        
        # In a real scenario, this would use the `code_analyzer` and `tool_registry` 
        # file_ops to read the repo. For this tool, we instruct the agent to use its own tools.
        
        prompt = (
            f"Target Repository Path: `{os.path.abspath(repo_path)}`\n"
            f"Issue / Request: {issue}\n\n"
            f"Use your tools to read the necessary files in the repository. "
            f"Then, formulate the exact code changes needed and present them as a git patch or updated file content."
        )

        result = self.agent.process(
            user_input=prompt,
            use_thinking_loop=True,
            max_tool_calls=10, # Needs to read files
            system_prompt_override=DEVOPS_PROMPT
        )
        
        if not result.error:
             content = (
                 f"# 🛠️ DevOps Autonomous Fix Proposal\n\n"
                 f"**Issue:** {issue}\n"
                 f"**Repository:** {repo_path}\n\n"
                 f"{result.answer}"
             )
             result.answer = content

        logger.info("🛠️ DevOps fix proposal complete.")
        return result
