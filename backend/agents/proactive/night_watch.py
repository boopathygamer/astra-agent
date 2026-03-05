"""
The Proactive 'Night Watch' Daemon
────────────────────────────────────
Runs in the background when the user is away. Scans the workspace,
runs tests, checks for vulnerabilities, and prepares a Morning Report.
"""

import time
import os
import logging
from pathlib import Path
from datetime import datetime

try:
    import schedule
except ImportError:
    schedule = None

from agents.controller import AgentController
from agents.tools.code_executor import CodeExecutor

logger = logging.getLogger(__name__)

class NightWatchDaemon:
    def __init__(self, agent_controller: AgentController):
        self.agent = agent_controller
        self.executor = CodeExecutor()
        self.workspace_dir = Path(os.getenv("LLM_WORKSPACE_DIR", "c:/llm"))
        self.report_path = self.workspace_dir / "morning_report.md"
        self.findings = []
        
    def _scan_for_python_files(self) -> list:
        """Find all python files ignoring virtual environments."""
        files = []
        for path in self.workspace_dir.rglob("*.py"):
            if "venv" not in path.parts and ".env" not in path.parts and ".git" not in path.parts:
                files.append(path)
        return files

    def run_nightly_audit(self):
        """Main execution sequence."""
        if schedule is None:
            logger.error("Schedule module not installed. Run `pip install schedule`.")
            return

        logger.info("🌙 Night Watch: Commencing nightly audit...")
        self.findings = []
        
        # 1. Run all unit tests
        self._execute_test_suite()
        
        # 2. Look for obvious code smells
        self._analyze_code_quality()
        
        # 3. Generate Report
        self._write_morning_report()
        
        logger.info("☀️ Night Watch: Audit complete. Morning report generated.")

    def _execute_test_suite(self):
        """Run pytest securely using the sandbox."""
        logger.info("  -> Running test suite...")
        try:
            # We assume pytest is installed. Execute it on the tests/ directory
            result = self.executor.execute(
                "import pytest, sys; sys.exit(pytest.main(['-q', 'tests/']))",
                timeout=60
            )
            
            if result.error or "failed" in (result.output or "").lower():
                self.findings.append(f"⚠️ **Test Failures Detected**:\n```text\n{result.output}\n```")
            else:
                self.findings.append("✅ All unit tests passed successfully.")
                
        except Exception as e:
            self.findings.append(f"❌ Failed to execute test suite: {e}")

    def _analyze_code_quality(self):
        """Use the agent to review one random complex file."""
        files = self._scan_for_python_files()
        if not files:
            return
            
        # Pick the largest file to analyze
        target_file = max(files, key=lambda f: f.stat().st_size)
        logger.info(f"  -> Deep analyzing {target_file.name} for code smells...")
        
        try:
            content = target_file.read_text(encoding='utf-8')
            # Extract just a chunk if it's too big to save context window
            chunk = content[:3000] 
            
            prompt = f"Act as an absolute genius Senior Principal Engineer. " \
                     f"Review this code snippet from heavily used file `{target_file.name}`. " \
                     f"Do not write code, just point out any obvious memory leaks, race conditions, " \
                     f"or O(N^2) loops. Be extremely concise.\n\nCode:\n{chunk}"
            
            # Use the brain's thinking loop for extreme accuracy
            response = self.agent.process(user_input=prompt, use_thinking_loop=True, max_tool_calls=1)
            
            self.findings.append(f"🤖 **Deep Analysis of `{target_file.name}`**:\n"
                                 f"> Confidence: {response.confidence:.2f}\n\n"
                                 f"{response.answer}")
                                 
        except Exception as e:
            logger.warning(f"Failed to analyze file: {e}")

    def _write_morning_report(self):
        """Compile findings into markdown."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        report = "# ☀️ System Morning Report\n"
        report += f"**Date:** {now}\n"
        report += f"**Workspace:** `{self.workspace_dir}`\n\n"
        
        report += "## Nightly Audit Findings\n\n"
        for finding in self.findings:
            report += f"{finding}\n\n---\n"
            
        report += "\n*Generated automatically by Universal AI Agent (Night Watch mode)*"
        
        self.report_path.write_text(report, encoding='utf-8')
        logger.info(f"Report saved to {self.report_path}")

    def start_daemon_blocking(self, trigger_time: str = "02:00"):
        """Block the thread and wait for the schedule."""
        if schedule is None:
            return
            
        schedule.every().day.at(trigger_time).do(self.run_nightly_audit)
        logger.info(f"🕰️ Night Watch Daemon started. Waiting for {trigger_time}...")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Night Watch manually terminated.")
