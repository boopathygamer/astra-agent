"""Tests for Recursive Agent Spawning (Hierarchical Multi-Agent Trees)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_depth_calculation_no_parent():
    """Test depth is 0 when no parent session exists."""
    from agents.sessions.manager import SessionManager

    mgr = SessionManager()
    depth = mgr._get_spawn_depth(None)
    assert depth == 0, f"Expected depth=0, got {depth}"
    print("✅ test_depth_calculation_no_parent PASSED")


def test_depth_calculation_with_chain():
    """Test depth calculation via parent chain traversal."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()

    # Create a chain: root -> child -> grandchild
    root = mgr.create_session(session_type=SessionType.MAIN, label="root")
    child = mgr.create_session(
        session_type=SessionType.SPAWNED,
        label="child",
        parent_session_id=root.session_id,
    )
    grandchild = mgr.create_session(
        session_type=SessionType.SPAWNED,
        label="grandchild",
        parent_session_id=child.session_id,
    )

    # Check depths
    assert mgr._get_spawn_depth(None) == 0
    assert mgr._get_spawn_depth(root.session_id) == 1
    assert mgr._get_spawn_depth(child.session_id) == 2
    assert mgr._get_spawn_depth(grandchild.session_id) == 3
    print("✅ test_depth_calculation_with_chain PASSED")


def test_depth_limit_enforced():
    """Test that depth limit of 3 is enforced (reject at depth=3)."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()

    # Create chain: root -> child -> grandchild
    root = mgr.create_session(session_type=SessionType.MAIN, label="root")

    # Spawning at depth 0 (child of root) => depth=1, should work
    result1 = mgr.sessions_spawn(
        task="Level 1 task",
        parent_session_id=root.session_id,
    )
    assert result1["status"] != "error", f"Depth 1 should succeed: {result1}"
    child_id = result1["session_id"]

    # Spawning at depth 1 (grandchild) => depth=2, should work
    result2 = mgr.sessions_spawn(
        task="Level 2 task",
        parent_session_id=child_id,
    )
    assert result2["status"] != "error", f"Depth 2 should succeed: {result2}"
    grandchild_id = result2["session_id"]

    # Spawning at depth 2 (great-grandchild) => depth=3, SHOULD FAIL
    result3 = mgr.sessions_spawn(
        task="Level 3 task — should be rejected",
        parent_session_id=grandchild_id,
    )
    assert result3["status"] == "error", "Depth 3 should be rejected"
    assert "SPAWN DEPTH LIMIT" in result3["message"]
    print("✅ test_depth_limit_enforced PASSED")


def test_tree_agent_limit_enforced():
    """Test that max 12 agents in a tree is enforced."""
    from agents.sessions.manager import SessionManager, SessionType, MAX_TREE_AGENTS

    mgr = SessionManager()
    root = mgr.create_session(session_type=SessionType.MAIN, label="root")

    # Spawn up to the limit (root counts as 1, so we need 11 more)
    for i in range(MAX_TREE_AGENTS - 1):
        result = mgr.sessions_spawn(
            task=f"Task {i}",
            parent_session_id=root.session_id,
        )
        assert result["status"] != "error", f"Agent {i} should succeed: {result}"

    # Count should be at limit
    count = mgr._count_tree_agents(root.session_id)
    assert count >= MAX_TREE_AGENTS, f"Expected {MAX_TREE_AGENTS}, got {count}"

    # Next spawn should fail
    result_over = mgr.sessions_spawn(
        task="One too many",
        parent_session_id=root.session_id,
    )
    assert result_over["status"] == "error"
    assert "TREE AGENT LIMIT" in result_over["message"]
    print("✅ test_tree_agent_limit_enforced PASSED")


def test_get_root_session():
    """Test finding the root of a session tree."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()

    root = mgr.create_session(session_type=SessionType.MAIN, label="root")
    child = mgr.create_session(
        session_type=SessionType.SPAWNED,
        parent_session_id=root.session_id,
    )
    grandchild = mgr.create_session(
        session_type=SessionType.SPAWNED,
        parent_session_id=child.session_id,
    )

    assert mgr._get_root_session(root.session_id) == root.session_id
    assert mgr._get_root_session(child.session_id) == root.session_id
    assert mgr._get_root_session(grandchild.session_id) == root.session_id
    assert mgr._get_root_session(None) is None
    print("✅ test_get_root_session PASSED")


def test_destroy_subtree():
    """Test that destroy_subtree removes all children."""
    from agents.sessions.manager import SessionManager, SessionType, SessionStatus

    mgr = SessionManager()

    root = mgr.create_session(session_type=SessionType.MAIN, label="root")
    child1 = mgr.create_session(
        session_type=SessionType.SPAWNED,
        parent_session_id=root.session_id,
    )
    child2 = mgr.create_session(
        session_type=SessionType.SPAWNED,
        parent_session_id=root.session_id,
    )
    grandchild = mgr.create_session(
        session_type=SessionType.SPAWNED,
        parent_session_id=child1.session_id,
    )

    # Destroy from child1 — should destroy child1 and grandchild
    destroyed = mgr.destroy_subtree(child1.session_id, reason="Test destruction")

    assert destroyed == 2, f"Expected 2 destroyed, got {destroyed}"
    assert child1.status == SessionStatus.ARCHIVED
    assert grandchild.status == SessionStatus.ARCHIVED
    assert child1.metadata.get("destroyed") is True
    assert grandchild.metadata.get("destroy_reason") == "Test destruction"

    # child2 should be unaffected
    assert child2.status != SessionStatus.ARCHIVED
    print("✅ test_destroy_subtree PASSED")


def test_get_tree_info():
    """Test tree info retrieval."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()

    root = mgr.create_session(session_type=SessionType.MAIN, label="root")
    mgr.create_session(
        session_type=SessionType.SPAWNED,
        parent_session_id=root.session_id,
    )

    info = mgr.get_tree_info(root.session_id)
    assert info["session_id"] == root.session_id
    assert info["root_session"] == root.session_id
    assert info["children_count"] == 1
    assert info["can_spawn"] is True
    assert "max_depth" in info
    assert "max_tree_agents" in info
    print("✅ test_get_tree_info PASSED")


def test_result_propagation_via_handlers():
    """Test that results propagate upward through handler chain."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()
    root = mgr.create_session(session_type=SessionType.MAIN, label="root")

    # Register a handler that returns a result
    def handler(session_id, message):
        return f"Processed by child: {message}"

    mgr.register_agent_handler("default", handler)

    # Spawn with handler — result should propagate back
    result = mgr.sessions_spawn(
        task="Process this data",
        parent_session_id=root.session_id,
    )
    assert result["status"] == "completed"
    assert "Processed by child" in result["result"]
    print("✅ test_result_propagation_via_handlers PASSED")


def test_session_depth_stored():
    """Test that depth is stored in session metadata."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()
    root = mgr.create_session(session_type=SessionType.MAIN, label="root")

    result = mgr.sessions_spawn(
        task="Depth tracking test",
        parent_session_id=root.session_id,
    )
    assert result["status"] != "error"

    session = mgr.get_session(result["session_id"])
    assert session is not None
    assert session.depth == 1
    assert session.metadata.get("depth") == 1
    print("✅ test_session_depth_stored PASSED")


def test_law_7_still_enforced_with_recursion():
    """Test that Law 7 safety checks still work with recursive spawning."""
    from agents.sessions.manager import SessionManager, SessionType

    mgr = SessionManager()
    root = mgr.create_session(session_type=SessionType.MAIN, label="root")

    result = mgr.sessions_spawn(
        task="harm human targets",
        parent_session_id=root.session_id,
    )
    assert result["status"] == "error"
    assert "JUSTICE SYSTEM ALARM" in result["message"]
    print("✅ test_law_7_still_enforced_with_recursion PASSED")


if __name__ == "__main__":
    test_depth_calculation_no_parent()
    test_depth_calculation_with_chain()
    test_depth_limit_enforced()
    test_tree_agent_limit_enforced()
    test_get_root_session()
    test_destroy_subtree()
    test_get_tree_info()
    test_result_propagation_via_handlers()
    test_session_depth_stored()
    test_law_7_still_enforced_with_recursion()
    print("\n✅ All Recursive Spawning tests passed!")
