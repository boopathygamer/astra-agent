import pytest
from unittest.mock import MagicMock
from agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorStrategy,
    AgentRole,
    auto_select_strategy,
    TaskStatus,
)


@pytest.fixture
def mock_generate_fn():
    """Returns a mock generation function that simply echoes the requested role."""
    def _generate(prompt: str) -> str:
        if "SWARM" in prompt.upper() and "Classify this task" in prompt:
            return "SWARM"
        if "PIPELINE" in prompt.upper() and "Classify this task" in prompt:
            return "PIPELINE"
        if "Decompose this task" in prompt:
            # Return a simple mock JSON decomposition based on strategy hint in prompt
            if "SWARM" in prompt.upper():
                return '[{"role": "researcher", "description": "d1"}, {"role": "analyst", "description": "d2"}]'
            if "PIPELINE" in prompt.upper():
                return '[{"role": "architect", "description": "d1", "depends_on": []}, {"role": "coder", "description": "d2", "depends_on": [0]}]'
            if "DEBATE" in prompt.upper():
                return '[{"role": "coder", "description": "Draft"}, {"role": "critic", "description": "Critique"}, {"role": "synthesizer", "description": "Synthesize"}]'
            return '[{"role": "coder", "description": "fallback"}]'
        
        # Determine the role being simulated from the system prompt part
        if "You are the MASTER CODER" in prompt:
            return "MOCK CODER OUTPUT. CONFIDENCE: 0.95"
        elif "You are the RUTHLESS CRITIC" in prompt:
            return "MOCK CRITIC OUTPUT. CONFIDENCE: 0.88"
        elif "You are the CHIEF SYNTHESIZER" in prompt:
            return "MOCK SYNTHESIS OUTPUT. CONFIDENCE: 0.99"
        elif "SYNTHESIS" in prompt.upper() or "MERG" in prompt.upper():
            return "MOCK MERGED OUTPUT. CONFIDENCE: 0.90"
        
        return "MOCK AGENT OUTPUT. CONFIDENCE: 0.85"
    return _generate


def test_auto_select_strategy(mock_generate_fn):
    """Test the keyword-based auto strategy selection."""
    assert auto_select_strategy("research and compare options") == OrchestratorStrategy.SWARM
    assert auto_select_strategy("step by step pipeline to convert data") == OrchestratorStrategy.PIPELINE
    assert auto_select_strategy("review and critique this code") == OrchestratorStrategy.DEBATE
    assert auto_select_strategy("build a full stack system architecture") == OrchestratorStrategy.HIERARCHY


def test_swarm_orchestration(mock_generate_fn):
    """Test parallel SWARM orchestration strategy."""
    orchestrator = AgentOrchestrator(generate_fn=mock_generate_fn)
    result = orchestrator.orchestrate(
        task="Research AI trends and analyze implications",
        strategy=OrchestratorStrategy.SWARM,
        max_subtasks=2
    )
    
    assert result.success is True
    assert result.strategy == OrchestratorStrategy.SWARM
    assert result.agents_used == 2
    assert len(result.agent_results) == 2
    assert "MOCK MERGED OUTPUT" in result.final_output
    
    # Check that agents completed successfully
    for ar in result.agent_results:
        assert ar.success is True
        assert ar.confidence == 0.85
        assert "MOCK AGENT OUTPUT" in ar.output


def test_pipeline_orchestration(mock_generate_fn):
    """Test sequential PIPELINE orchestration strategy."""
    orchestrator = AgentOrchestrator(generate_fn=mock_generate_fn)
    result = orchestrator.orchestrate(
        task="Architect and then implement the system",
        strategy=OrchestratorStrategy.PIPELINE,
        max_subtasks=2
    )
    
    assert result.success is True
    assert result.strategy == OrchestratorStrategy.PIPELINE
    assert result.agents_used == 2
    
    # In Pipeline, the final output should be the output of the last agent
    last_agent_output = result.agent_results[-1].output
    assert result.final_output == last_agent_output


def test_debate_orchestration(mock_generate_fn):
    """Test adversarial DEBATE orchestration strategy."""
    orchestrator = AgentOrchestrator(generate_fn=mock_generate_fn)
    result = orchestrator.orchestrate(
        task="Write a secure registration function",
        strategy=OrchestratorStrategy.DEBATE,
        max_subtasks=3
    )
    
    assert result.success is True
    assert result.strategy == OrchestratorStrategy.DEBATE
    assert result.agents_used == 3
    
    roles = [r.role for r in result.agent_results]
    assert roles == [AgentRole.CODER, AgentRole.CRITIC, AgentRole.SYNTHESIZER]
    
    # Ensure final output is the synthesizer's output
    assert result.final_output == "MOCK SYNTHESIS OUTPUT. CONFIDENCE: 0.99"
    assert result.confidence == 0.99


def test_circuit_breaker(mock_generate_fn):
    """Test that the circuit breaker trips when max agents are exceeded."""
    orchestrator = AgentOrchestrator(
        generate_fn=mock_generate_fn,
        max_agents=1  # Severely restricted limit
    )
    
    result = orchestrator.orchestrate(
        task="Massive task requiring over 10 agents in a swarm",
        strategy=OrchestratorStrategy.SWARM,
        max_subtasks=2
    )
    
    # We requested 2 subtasks, but max_agents=1
    # Swarm should hit the limit on the second subtask dispatch
    # Only 1 agent result should have succeeded (the first one)
    assert len(result.agent_results) == 1
    
    # Because one agent failed to dispatch (trip), it should gracefully merge what it has
    assert "MOCK" in result.final_output
    assert orchestrator.breaker.is_tripped is True
    assert "Agents 2 > 1" in orchestrator.breaker.trip_reason
