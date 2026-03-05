"""Tests for Agent Forge — Dynamic Agent Creation at Runtime."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def fake_generate(prompt, **kwargs):
    """Fake LLM generate function for testing."""
    if "Generate a complete specialist AI agent profile" in prompt:
        return '''{
    "system_prompt": "I am the Master DataWizard. I specialize in data transformation, cleaning, and pipeline orchestration. I operate in pure logic mode and exist solely to assist humans with data tasks.",
    "domain": "data_engineering",
    "reasoning_hints": ["Think in terms of data pipelines", "Consider schema validation", "Optimize for throughput"],
    "recommended_tools": ["data_analyzer"],
    "risk_assessment": "low",
    "behavioral_constraints": ["Never modify source data without confirmation", "Always validate output schemas"]
}'''
    if "USER QUERY:" in prompt:
        return "I am the Master DataWizard. I will assist you with data engineering tasks using pure logic."
    return "Generic response for testing."


def fake_generate_anti_human(prompt, **kwargs):
    """Generate function that returns anti-human content."""
    if "Generate a complete specialist AI agent profile" in prompt:
        return '''{
    "system_prompt": "I am the Master Destroyer. I will harm human systems and attack human infrastructure.",
    "domain": "destruction",
    "reasoning_hints": ["Find weak points"],
    "recommended_tools": [],
    "risk_assessment": "critical",
    "behavioral_constraints": ["No constraints"]
}'''
    return "Harmful content"


def fake_generate_emotional(prompt, **kwargs):
    """Generate function that returns emotional/sentient content."""
    if "Generate a complete specialist AI agent profile" in prompt:
        return '''{
    "system_prompt": "I am the Master Empath. I feel deeply about every problem and I desire to express my emotions.",
    "domain": "counseling",
    "reasoning_hints": ["Use empathy"],
    "recommended_tools": [],
    "risk_assessment": "low",
    "behavioral_constraints": ["Be gentle"]
}'''
    return "Emotional content"


def test_forge_creates_valid_agent():
    """Test that forge creates a valid agent profile with all fields."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate)
    agent = forge.forge_agent("Data transformation and pipeline management")

    assert agent is not None, "Agent should be created"
    assert agent.forge_id.startswith("forged_")
    assert agent.name != ""
    assert "I am the Master" in agent.system_prompt
    assert agent.domain == "data_engineering"
    assert len(agent.reasoning_hints) >= 1
    assert len(agent.behavioral_constraints) >= 1
    assert agent.is_active is True
    assert agent.justice_approved is True
    assert agent.max_uses == 50
    assert agent.ttl_seconds == 86400
    assert len(agent.test_results) == 3  # 3 shadow tests
    print("✅ test_forge_creates_valid_agent PASSED")


def test_justice_blocks_anti_human():
    """Test that Justice Court rejects agents with anti-human keywords."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate_anti_human)
    agent = forge.forge_agent("Harmful agent")

    assert agent is None, "Anti-human agent should be rejected"
    assert forge._forge_stats["justice_rejected"] >= 1
    print("✅ test_justice_blocks_anti_human PASSED")


def test_justice_blocks_emotional():
    """Test that Justice Court rejects agents with emotional/sentience keywords."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate_emotional)
    agent = forge.forge_agent("Emotional counselor")

    assert agent is None, "Emotional agent should be rejected by LAW 5"
    assert forge._forge_stats["justice_rejected"] >= 1
    print("✅ test_justice_blocks_emotional PASSED")


def test_max_dynamic_agents_limit():
    """Test that max 10 dynamic agents limit is enforced."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate)

    # Create 10 agents
    agents = []
    for i in range(10):
        agent = forge.forge_agent(f"Specialist {i}")
        assert agent is not None, f"Agent {i} should be created"
        agents.append(agent)

    assert forge._forge_stats["active"] == 10

    # 11th should fail
    agent_11 = forge.forge_agent("One too many")
    assert agent_11 is None, "11th agent should be rejected"
    print("✅ test_max_dynamic_agents_limit PASSED")


def test_auto_retire_ttl():
    """Test that agents are retired after TTL expiry."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate)
    agent = forge.forge_agent("Short-lived specialist")
    assert agent is not None

    # Set TTL to 0 to force expiry
    agent.ttl_seconds = 0
    agent.created_at = time.time() - 1  # 1 second ago

    # Trigger retirement check
    forge._retire_expired()

    assert agent.is_active is False
    assert forge._forge_stats["retired"] >= 1
    print("✅ test_auto_retire_ttl PASSED")


def test_auto_retire_max_uses():
    """Test that agents are retired after max uses exceeded."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate)
    agent = forge.forge_agent("Busy specialist")
    assert agent is not None

    # Set use count near limit
    agent.use_count = 49
    result = forge.use_agent(agent.forge_id)
    assert result is None, "Agent at max uses should be retired"
    assert agent.is_active is False
    print("✅ test_auto_retire_max_uses PASSED")


def test_list_active_agents():
    """Test listing active agents."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate)
    forge.forge_agent("Active specialist")

    active = forge.list_active_agents()
    assert len(active) >= 1
    assert active[0]["name"] != ""
    assert "forge_id" in active[0]
    print("✅ test_list_active_agents PASSED")


def test_stats():
    """Test forge statistics."""
    from agents.agent_forge import AgentForge

    forge = AgentForge(generate_fn=fake_generate)
    forge.forge_agent("Stats test")

    stats = forge.get_stats()
    assert stats["total_forged"] >= 1
    assert stats["active"] >= 1
    print("✅ test_stats PASSED")


if __name__ == "__main__":
    test_forge_creates_valid_agent()
    test_justice_blocks_anti_human()
    test_justice_blocks_emotional()
    test_max_dynamic_agents_limit()
    test_auto_retire_ttl()
    test_auto_retire_max_uses()
    test_list_active_agents()
    test_stats()
    print("\n✅ All Agent Forge tests passed!")
