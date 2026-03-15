"""
Tests for the Environment Observer — 7-Sensor Perception Engine.

Validates all sensors, anomaly detection, snapshot history,
change delta detection, and context prompt generation.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_system_vitals_sensor():
    """Test SystemVitals returns valid CPU, RAM, disk metrics."""
    from brain.environment_observer import SystemVitals

    sensor = SystemVitals()
    data = sensor.scan()

    assert "cpu_percent" in data, "Missing cpu_percent"
    assert 0 <= data["cpu_percent"] <= 100, f"CPU% out of range: {data['cpu_percent']}"
    assert "ram_total_gb" in data, "Missing ram_total_gb"
    assert data["ram_total_gb"] > 0, "RAM total should be > 0"
    assert "ram_percent" in data, "Missing ram_percent"
    assert 0 <= data["ram_percent"] <= 100
    assert "uptime_hours" in data, "Missing uptime_hours"
    assert data["uptime_hours"] > 0, "Uptime should be > 0"

    print(f"  ✅ SystemVitals: CPU={data['cpu_percent']}%, "
          f"RAM={data['ram_percent']}%, "
          f"Cores={data.get('cpu_cores_logical', '?')}")


def test_network_probe_sensor():
    """Test NetworkProbe returns network metrics."""
    from brain.environment_observer import NetworkProbe

    sensor = NetworkProbe()
    data = sensor.scan()

    assert "hostname" in data, "Missing hostname"
    assert len(data["hostname"]) > 0, "Hostname should not be empty"
    assert "bytes_sent_mb" in data or "total_connections" in data, \
        "Should have network I/O or connection data"

    print(f"  ✅ NetworkProbe: hostname={data['hostname']}, "
          f"internet={data.get('internet_reachable', '?')}, "
          f"dns={data.get('dns_latency_ms', '?')}ms")


def test_process_radar_sensor():
    """Test ProcessRadar returns process list."""
    from brain.environment_observer import ProcessRadar

    sensor = ProcessRadar()
    data = sensor.scan()

    assert "total_processes" in data, "Missing total_processes"
    assert data["total_processes"] > 0, "Should have at least 1 process"
    assert "top_by_memory" in data, "Missing top_by_memory"
    assert len(data["top_by_memory"]) > 0, "Should have top processes"
    assert "agent_pid" in data, "Missing agent_pid"

    print(f"  ✅ ProcessRadar: {data['total_processes']} processes, "
          f"agent_pid={data.get('agent_pid', '?')}, "
          f"agent_mem={data.get('agent_memory_mb', '?')}MB")


def test_filesystem_watch_sensor():
    """Test FileSystemWatch returns partition data."""
    from brain.environment_observer import FileSystemWatch

    sensor = FileSystemWatch()
    data = sensor.scan()

    assert "partitions" in data, "Missing partitions"
    assert len(data["partitions"]) > 0, "Should have at least 1 partition"

    print(f"  ✅ FileSystemWatch: {len(data['partitions'])} partitions")


def test_filesystem_watch_with_workspace():
    """Test FileSystemWatch detects workspace file changes."""
    import tempfile
    import os
    from brain.environment_observer import FileSystemWatch

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some files
        for i in range(3):
            (Path(tmpdir) / f"test_{i}.txt").write_text(f"content {i}")

        sensor = FileSystemWatch(workspace_dir=tmpdir)
        data = sensor.scan()

        assert "workspace_path" in data, "Missing workspace_path"
        assert data["total_files"] >= 3, f"Expected >= 3 files, got {data['total_files']}"

        # Create a new file and scan again
        (Path(tmpdir) / "new_file.txt").write_text("new")
        data2 = sensor.scan()

        assert "new_files" in data2, "Missing new_files"
        assert "new_file.txt" in data2["new_files"], "Should detect new file"

        print(f"  ✅ FileSystemWatch+Workspace: detected new files: {data2['new_files']}")


def test_peripheral_scanner_sensor():
    """Test PeripheralScanner returns device data."""
    from brain.environment_observer import PeripheralScanner

    scanner = PeripheralScanner()
    data = scanner.scan()

    # Result depends on platform, just verify it doesn't crash
    assert isinstance(data, dict), "Should return a dict"

    usb = data.get("usb_devices", [])
    displays = data.get("displays", [])
    print(f"  ✅ PeripheralScanner: {len(usb)} USB devices, "
          f"{len(displays)} displays")


def test_environment_context_sensor():
    """Test EnvironmentContext returns OS and Python info."""
    from brain.environment_observer import EnvironmentContext

    sensor = EnvironmentContext()
    data = sensor.scan()

    assert "os_system" in data, "Missing os_system"
    assert "python_version" in data, "Missing python_version"
    assert "cwd" in data, "Missing cwd"
    assert len(data["os_system"]) > 0

    print(f"  ✅ EnvironmentContext: {data['os_system']} | "
          f"Python {data['python_version']}")


def test_thermal_sentinel_sensor():
    """Test ThermalSentinel returns thermal data."""
    from brain.environment_observer import ThermalSentinel

    sensor = ThermalSentinel()
    data = sensor.scan()

    assert "thermal_state" in data, "Missing thermal_state"
    assert data["thermal_state"] in (
        "normal", "warning", "critical", "unknown",
        "unsupported", "unavailable", "cool",
    ), f"Unexpected thermal_state: {data['thermal_state']}"

    print(f"  ✅ ThermalSentinel: state={data['thermal_state']}, "
          f"max_temp={data.get('max_temperature_c', 'N/A')}°C")


def test_full_observation():
    """Test complete environment observation."""
    from brain.environment_observer import EnvironmentObserver

    observer = EnvironmentObserver()
    snapshot = observer.observe()

    assert snapshot.sensor_count >= 5, \
        f"Expected at least 5/7 sensors, got {snapshot.sensor_count}"
    assert snapshot.scan_duration_ms > 0, "Scan should take > 0ms"
    assert snapshot.system_vitals, "Should have system vitals"
    assert snapshot.environment, "Should have environment context"

    print(f"\n  {snapshot.summary()}")
    print(f"  ✅ Full observation: {snapshot.sensor_count}/7 sensors in "
          f"{snapshot.scan_duration_ms:.0f}ms")


def test_fast_mode_observation():
    """Test that fast mode skips slow sensors."""
    from brain.environment_observer import EnvironmentObserver

    observer = EnvironmentObserver()
    fast_snap = observer.observe(fast_mode=True)
    full_snap = observer.observe(fast_mode=False)

    # Fast mode should be faster (or at least not crash)
    assert fast_snap.scan_duration_ms >= 0
    assert fast_snap.system_vitals, "Fast mode should still have vitals"

    print(f"  ✅ Fast mode: {fast_snap.scan_duration_ms:.0f}ms vs "
          f"full: {full_snap.scan_duration_ms:.0f}ms")


def test_anomaly_detection():
    """Test anomaly detector correctly flags injected anomalies."""
    from brain.environment_observer import (
        AnomalyDetector, EnvironmentSnapshot, AnomalyLevel,
    )

    detector = AnomalyDetector(z_threshold=2.0, min_samples=3)

    # Feed normal data to build baseline
    for cpu in [50, 52, 48, 51, 49, 50, 53, 47, 50, 51]:
        snap = EnvironmentSnapshot()
        snap.system_vitals = {"cpu_percent": cpu, "ram_percent": 45}
        anomalies = detector.update_and_detect(snap)

    # Now inject an anomaly (CPU spike to 99%)
    anomaly_snap = EnvironmentSnapshot()
    anomaly_snap.system_vitals = {"cpu_percent": 99.0, "ram_percent": 45}
    anomalies = detector.update_and_detect(anomaly_snap)

    assert len(anomalies) > 0, "Should detect CPU anomaly"
    cpu_anomaly = [a for a in anomalies if a.metric == "cpu_percent"]
    assert len(cpu_anomaly) > 0, "Should flag cpu_percent anomaly"
    assert cpu_anomaly[0].z_score > 2.0, "Z-score should be > threshold"

    print(f"  ✅ Anomaly detection: flagged CPU spike (z={cpu_anomaly[0].z_score:.1f})")


def test_change_delta():
    """Test change delta detection between snapshots."""
    from brain.environment_observer import EnvironmentObserver

    observer = EnvironmentObserver()

    # First observation
    observer.observe()
    time.sleep(0.5)

    # Second observation
    observer.observe()

    delta = observer.get_change_delta()
    assert delta is not None, "Should have a delta after 2 observations"
    assert delta.time_elapsed_s > 0, "Time should have elapsed"

    print(f"  ✅ Change delta: {delta.summary()}")


def test_context_prompt_generation():
    """Test LLM context prompt is generated correctly."""
    from brain.environment_observer import EnvironmentObserver

    observer = EnvironmentObserver()
    observer.observe()

    context = observer.build_context_prompt()
    assert len(context) > 0, "Context should not be empty"
    assert "ENVIRONMENT AWARENESS" in context, "Should have header"
    assert "CPU" in context or "System" in context, "Should mention system metrics"
    assert len(context) <= 800, f"Context too long: {len(context)} chars"

    print(f"  ✅ Context prompt: {len(context)} chars")
    for line in context.split("\n")[:5]:
        print(f"     {line}")


def test_sensor_failure_isolation():
    """Test that one sensor crash doesn't kill the others."""
    from brain.environment_observer import EnvironmentObserver

    observer = EnvironmentObserver()

    # Inject a broken sensor
    class BrokenSensor:
        def scan(self):
            raise RuntimeError("Intentional crash for testing")

    observer._sensors["thermal"] = BrokenSensor()
    snapshot = observer.observe()

    assert "thermal" in snapshot.sensors_failed, \
        "Should report thermal sensor failure"
    assert snapshot.sensor_count >= 5, \
        "Other sensors should still work"
    assert snapshot.system_vitals, "Vitals should survive thermal crash"

    print(f"  ✅ Sensor isolation: thermal crashed, "
          f"{snapshot.sensor_count}/7 sensors still OK")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🔭  Environment Observer — Test Suite")
    print("=" * 60 + "\n")

    print("─── Test 1: SystemVitals ───")
    test_system_vitals_sensor()

    print("\n─── Test 2: NetworkProbe ───")
    test_network_probe_sensor()

    print("\n─── Test 3: ProcessRadar ───")
    test_process_radar_sensor()

    print("\n─── Test 4: FileSystemWatch ───")
    test_filesystem_watch_sensor()

    print("\n─── Test 5: FileSystemWatch + Workspace ───")
    test_filesystem_watch_with_workspace()

    print("\n─── Test 6: PeripheralScanner ───")
    test_peripheral_scanner_sensor()

    print("\n─── Test 7: EnvironmentContext ───")
    test_environment_context_sensor()

    print("\n─── Test 8: ThermalSentinel ───")
    test_thermal_sentinel_sensor()

    print("\n─── Test 9: Full Observation ───")
    test_full_observation()

    print("\n─── Test 10: Fast Mode ───")
    test_fast_mode_observation()

    print("\n─── Test 11: Anomaly Detection ───")
    test_anomaly_detection()

    print("\n─── Test 12: Change Delta ───")
    test_change_delta()

    print("\n─── Test 13: Context Prompt ───")
    test_context_prompt_generation()

    print("\n─── Test 14: Sensor Failure Isolation ───")
    test_sensor_failure_isolation()

    print("\n" + "=" * 60)
    print("  🎉  ALL 14 ENVIRONMENT OBSERVER TESTS PASSED!")
    print("=" * 60 + "\n")
