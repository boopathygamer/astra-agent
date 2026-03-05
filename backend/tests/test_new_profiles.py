import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.controller import AgentController
from agents.profiles.multi_agent_orchestrator import MultiAgentOrchestrator
from agents.profiles.devops_reviewer import DevOpsReviewer

def test_multi_agent_orchestrator_initializes():
    print("Testing MultiAgentOrchestrator initialization...")
    def mock_generate(prompt):
        return "mock response"
        
    controller = AgentController(generate_fn=mock_generate)
    orchestrator = MultiAgentOrchestrator(controller)
    assert orchestrator.agent is not None
    print("MultiAgentOrchestrator initialized successfully.")

def test_devops_reviewer_initializes():
    print("Testing DevOpsReviewer initialization...")
    def mock_generate(prompt):
        return "mock response"
        
    controller = AgentController(generate_fn=mock_generate)
    reviewer = DevOpsReviewer(controller)
    assert reviewer.agent is not None
    print("DevOpsReviewer initialized successfully.")

if __name__ == "__main__":
    test_multi_agent_orchestrator_initializes()
    test_devops_reviewer_initializes()
    print("All basic initialization tests passed.")
