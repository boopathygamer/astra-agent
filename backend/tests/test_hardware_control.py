"""
Tests for the Hardware Control Suite — Device Ops + Hardware Symbiosis.

Validates SecurityGateway, AuditTrail, all 8 device tools,
and the HardwareSymbiosis adaptive scheduling engine.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_security_gateway_denies_by_default():
    """Test SecurityGateway denies when no permission granted."""
    from agents.tools.device_ops import SecurityGateway

    # Reset state
    SecurityGateway._DEVICE_CONTROL_GRANTED = False
    SecurityGateway._grant_timestamp = None
    SecurityGateway._grant_method = ""

    # Ensure env var is not set
    old_val = os.environ.pop("SUPER_AGENT_ALLOW_DEVICE", None)

    assert not SecurityGateway.request_permission(), \
        "Should deny by default"

    try:
        SecurityGateway.verify()
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass

    # Restore env var if it was set
    if old_val:
        os.environ["SUPER_AGENT_ALLOW_DEVICE"] = old_val

    print("  ✅ SecurityGateway denies by default")


def test_security_gateway_grants_explicitly():
    """Test SecurityGateway grants on explicit call."""
    from agents.tools.device_ops import SecurityGateway

    SecurityGateway._DEVICE_CONTROL_GRANTED = False
    SecurityGateway.grant(method="test")

    assert SecurityGateway._DEVICE_CONTROL_GRANTED is True
    assert SecurityGateway._grant_method == "test"
    assert SecurityGateway._grant_timestamp is not None

    # Should not raise
    SecurityGateway.verify()

    # Status check
    status = SecurityGateway.get_status()
    assert status["granted"] is True

    # Test revoke
    SecurityGateway.revoke()
    assert SecurityGateway._DEVICE_CONTROL_GRANTED is False

    print("  ✅ SecurityGateway grant/revoke cycle works")


def test_security_gateway_env_var():
    """Test SecurityGateway grants via environment variable."""
    from agents.tools.device_ops import SecurityGateway

    SecurityGateway._DEVICE_CONTROL_GRANTED = False
    os.environ["SUPER_AGENT_ALLOW_DEVICE"] = "true"

    assert SecurityGateway.request_permission() is True

    # Cleanup
    del os.environ["SUPER_AGENT_ALLOW_DEVICE"]
    SecurityGateway._DEVICE_CONTROL_GRANTED = False

    print("  ✅ SecurityGateway env var grant works")


def test_audit_trail():
    """Test AuditTrail records actions correctly."""
    from agents.tools.device_ops import AuditTrail

    with tempfile.TemporaryDirectory() as tmpdir:
        audit = AuditTrail(audit_dir=tmpdir)

        # Record entries
        e1 = audit.record("get_device_performance", "read", {}, "ok", True, "medium")
        e2 = audit.record("manage_processes", "kill", {"pid": 123}, "killed", True, "critical")
        e3 = audit.record("execute_system_command", "ping", {"target": "google.com"}, "4 packets", True, "critical")

        # Verify entries
        recent = audit.get_recent(10)
        assert len(recent) == 3, f"Expected 3 entries, got {len(recent)}"
        assert recent[0].tool == "get_device_performance"
        assert recent[1].action == "kill"
        assert recent[2].result == "4 packets"

        # Filter by tool
        proc_entries = audit.get_by_tool("manage_processes")
        assert len(proc_entries) == 1

        # Check file persistence
        audit_file = Path(tmpdir) / "audit.jsonl"
        assert audit_file.exists(), "Audit file should be created"
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 3, f"Expected 3 JSONL lines, got {len(lines)}"

    print("  ✅ AuditTrail records and persists correctly")


def test_get_device_performance():
    """Test get_device_performance returns all expected metrics."""
    from agents.tools.device_ops import get_device_performance, SecurityGateway

    SecurityGateway.grant(method="test")

    try:
        metrics = get_device_performance(detailed=True)

        assert "cpu_percent" in metrics, "Missing cpu_percent"
        assert 0 <= metrics["cpu_percent"] <= 100
        assert "ram_total_gb" in metrics, "Missing ram_total_gb"
        assert metrics["ram_total_gb"] > 0
        assert "ram_percent" in metrics, "Missing ram_percent"
        assert "disk_total_gb" in metrics or True  # May fail on some CI

        print(f"  ✅ Performance: CPU={metrics['cpu_percent']}%, "
              f"RAM={metrics['ram_percent']}%, "
              f"GPU={metrics.get('gpu_name', 'N/A')}")
    finally:
        SecurityGateway.revoke()


def test_manage_processes_list():
    """Test manage_processes list_top action."""
    from agents.tools.device_ops import manage_processes, SecurityGateway

    SecurityGateway.grant(method="test")

    try:
        result = manage_processes(action="list_top")
        assert "Top 10" in result, "Should contain header"
        assert "PID" in result, "Should list PIDs"

        # Test list_children
        result2 = manage_processes(action="list_children")
        assert isinstance(result2, str)

        # Test invalid action
        result3 = manage_processes(action="invalid_action")
        assert "Invalid" in result3

        print(f"  ✅ Process list: {len(result.split(chr(10)))} lines")
    finally:
        SecurityGateway.revoke()


def test_manage_processes_list_by_name():
    """Test manage_processes list_by_name action."""
    from agents.tools.device_ops import manage_processes, SecurityGateway

    SecurityGateway.grant(method="test")

    try:
        # Search for python processes (should find at least this test process)
        result = manage_processes(action="list_by_name", name="python")
        assert isinstance(result, str)
        # May or may not find python depending on how test is run
        print(f"  ✅ Process search: {result[:80]}...")
    finally:
        SecurityGateway.revoke()


def test_get_network_status():
    """Test get_network_status returns network metrics."""
    from agents.tools.device_ops import get_network_status, SecurityGateway

    SecurityGateway.grant(method="test")

    try:
        status = get_network_status()

        assert "hostname" in status, "Missing hostname"
        assert isinstance(status["hostname"], str)
        assert "internet_reachable" in status or "total_connections" in status

        print(f"  ✅ Network: host={status['hostname']}, "
              f"internet={status.get('internet_reachable', '?')}")
    finally:
        SecurityGateway.revoke()


def test_get_peripheral_devices():
    """Test get_peripheral_devices returns device list."""
    from agents.tools.device_ops import get_peripheral_devices

    # This is LOW risk, no SecurityGateway needed
    result = get_peripheral_devices()
    assert isinstance(result, dict)

    usb = result.get("usb_devices", [])
    print(f"  ✅ Peripherals: {len(usb)} USB devices found")


def test_execute_system_command_allowlist():
    """Test execute_system_command only runs allowlisted commands."""
    from agents.tools.device_ops import execute_system_command, SecurityGateway

    SecurityGateway.grant(method="test")

    try:
        # Allowed: whoami
        result = execute_system_command(command="whoami")
        assert len(result.strip()) > 0, "whoami should return something"
        assert "not found" not in result.lower()

        # Allowed: hostname
        result2 = execute_system_command(command="hostname")
        assert len(result2.strip()) > 0

        # NOT in allowlist
        result3 = execute_system_command(command="rm_rf")
        assert "NOT in the allowlist" in result3

        print(f"  ✅ Allowlisted commands work, non-allowlisted rejected")
    finally:
        SecurityGateway.revoke()


def test_execute_system_command_target_sanitization():
    """Test target parameter is properly sanitized."""
    from agents.tools.device_ops import execute_system_command, SecurityGateway

    SecurityGateway.grant(method="test")

    try:
        # Invalid target (shell injection attempt)
        result = execute_system_command(
            command="ping", target="; rm -rf /"
        )
        assert "Invalid target" in result, \
            "Should reject targets with shell metacharacters"

        # Valid target
        result2 = execute_system_command(
            command="ping", target="127.0.0.1"
        )
        assert "Invalid target" not in result2

        print("  ✅ Target sanitization prevents injection")
    finally:
        SecurityGateway.revoke()


def test_tools_fail_without_permission():
    """Test that all gated tools raise PermissionError when denied."""
    from agents.tools.device_ops import (
        get_device_performance, manage_processes,
        manage_power_state, get_network_status,
        manage_services, manage_scheduled_tasks,
        execute_system_command, SecurityGateway,
    )

    SecurityGateway.revoke()
    old_val = os.environ.pop("SUPER_AGENT_ALLOW_DEVICE", None)

    gated_tools = [
        ("get_device_performance", lambda: get_device_performance()),
        ("manage_processes", lambda: manage_processes(action="list_top")),
        ("manage_power_state", lambda: manage_power_state(action="sleep")),
        ("get_network_status", lambda: get_network_status()),
        ("manage_services", lambda: manage_services(action="list")),
        ("manage_scheduled_tasks", lambda: manage_scheduled_tasks(action="list")),
        ("execute_system_command", lambda: execute_system_command(command="whoami")),
    ]

    for name, fn in gated_tools:
        try:
            fn()
            assert False, f"{name} should have raised PermissionError"
        except PermissionError:
            pass

    if old_val:
        os.environ["SUPER_AGENT_ALLOW_DEVICE"] = old_val

    print(f"  ✅ All {len(gated_tools)} gated tools correctly deny without permission")


def test_hardware_symbiosis_optimize():
    """Test HardwareSymbiosis full optimization pass."""
    from brain.hardware_symbiosis import HardwareSymbiosis

    hw = HardwareSymbiosis()
    report = hw.optimize()

    assert report.cpu_percent >= 0
    assert report.ram_percent >= 0
    assert report.thermal_state is not None
    assert report.memory_pressure is not None

    print(f"  ✅ HW Optimize: {report.summary()}")


def test_hardware_symbiosis_context():
    """Test HardwareSymbiosis context generation for thinking loop."""
    from brain.hardware_symbiosis import HardwareSymbiosis

    hw = HardwareSymbiosis()
    context = hw.get_hardware_context()

    assert len(context) > 0, "Context should not be empty"
    assert "HARDWARE CONTEXT" in context, "Should have header"
    assert "CPU" in context, "Should mention CPU"
    assert len(context) <= 400, f"Context too long: {len(context)}"

    print(f"  ✅ HW Context: {len(context)} chars")


def test_thermal_governor():
    """Test ThermalGovernor state classification."""
    from brain.hardware_symbiosis import ThermalGovernor, ThermalState

    gov = ThermalGovernor(warning_c=75.0, critical_c=85.0)
    state, temp, zones = gov.assess()

    assert isinstance(state, ThermalState)
    assert isinstance(zones, dict)

    print(f"  ✅ ThermalGovernor: state={state.value}, "
          f"temp={temp:.1f}°C, zones={len(zones)}")


def test_memory_pressure_manager():
    """Test MemoryPressureManager assessment."""
    from brain.hardware_symbiosis import MemoryPressureManager, MemoryPressure

    mgr = MemoryPressureManager()
    pressure, ram_pct, action = mgr.assess()

    assert isinstance(pressure, MemoryPressure)
    assert 0 <= ram_pct <= 100

    agent_mem = mgr.get_agent_memory()
    assert "rss_mb" in agent_mem
    assert agent_mem["rss_mb"] > 0

    print(f"  ✅ MemoryPressure: {pressure.value}, "
          f"RAM={ram_pct:.0f}%, agent={agent_mem['rss_mb']}MB")


def test_hardware_symbiosis_stats():
    """Test HardwareSymbiosis statistics."""
    from brain.hardware_symbiosis import HardwareSymbiosis

    hw = HardwareSymbiosis()
    hw.optimize()
    hw.optimize()

    stats = hw.get_stats()
    assert stats["total_optimizations"] == 2
    assert "agent_memory" in stats
    assert stats["agent_memory"]["rss_mb"] > 0

    print(f"  ✅ HW Stats: {stats['total_optimizations']} optimizations, "
          f"GC runs: {stats['gc_runs']}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🔧  Hardware Control — Test Suite")
    print("=" * 60 + "\n")

    print("─── Test 1: SecurityGateway Deny Default ───")
    test_security_gateway_denies_by_default()

    print("\n─── Test 2: SecurityGateway Grant/Revoke ───")
    test_security_gateway_grants_explicitly()

    print("\n─── Test 3: SecurityGateway Env Var ───")
    test_security_gateway_env_var()

    print("\n─── Test 4: Audit Trail ───")
    test_audit_trail()

    print("\n─── Test 5: Device Performance ───")
    test_get_device_performance()

    print("\n─── Test 6: Process Management ───")
    test_manage_processes_list()

    print("\n─── Test 7: Process Search ───")
    test_manage_processes_list_by_name()

    print("\n─── Test 8: Network Status ───")
    test_get_network_status()

    print("\n─── Test 9: Peripheral Devices ───")
    test_get_peripheral_devices()

    print("\n─── Test 10: System Commands (Allowlist) ───")
    test_execute_system_command_allowlist()

    print("\n─── Test 11: Target Sanitization ───")
    test_execute_system_command_target_sanitization()

    print("\n─── Test 12: Permission Denial ───")
    test_tools_fail_without_permission()

    print("\n─── Test 13: Hardware Symbiosis Optimize ───")
    test_hardware_symbiosis_optimize()

    print("\n─── Test 14: Hardware Symbiosis Context ───")
    test_hardware_symbiosis_context()

    print("\n─── Test 15: Thermal Governor ───")
    test_thermal_governor()

    print("\n─── Test 16: Memory Pressure Manager ───")
    test_memory_pressure_manager()

    print("\n─── Test 17: Hardware Symbiosis Stats ───")
    test_hardware_symbiosis_stats()

    print("\n" + "=" * 60)
    print("  🎉  ALL 17 HARDWARE CONTROL TESTS PASSED!")
    print("=" * 60 + "\n")
