import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.controller import AgentController
from agents.experts.router import DomainRouter
from brain.reasoning import ReasoningTrace
from brain.thinking_loop import ThinkingResult, ThinkingStep
from brain.epistemic_checker import EpistemicChecker
from core.model_providers import GenerationResult

def test_epistemic_checker():
    print("Testing EpistemicChecker...")
    def mock_generate(prompt):
        if "Extract" in prompt:
            return "1. The sky is green."
        return "STATUS: HALLUCINATION"

    checker = EpistemicChecker(generate_fn=mock_generate)
    passed, report = checker.check_claims("The sky is green because of copper.")
    assert passed is False
    assert "HALLUCINATION" in report
    print("EpistemicChecker initialization passed.")

def test_controller_initialization():
    print("Testing Universal Controller Enhancements...")
    def mock_generate(prompt):
        return "mock response"
        
    controller = AgentController(generate_fn=mock_generate)
    assert controller.domain_router is not None
    assert controller.advanced_reasoner is not None
    print("AgentController Universal hooks initialized successfully.")

if __name__ == "__main__":
    test_epistemic_checker()
    test_controller_initialization()
    print("All Universal Feature initialization tests passed.")
