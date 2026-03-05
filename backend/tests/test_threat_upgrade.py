"""Verification test for the upgraded threat engine."""
import sys

def test_all():
    errors = []
    
    # Test 1: threat_guard tools
    try:
        from agents.tools.threat_guard import (
            threat_scan_file, threat_scan_url, threat_scan_content,
            threat_quarantine, threat_destroy,
            threat_rollback, threat_kill_process, threat_reimage,
        )
        print("✅ threat_guard: 8 tools loaded OK")
    except Exception as e:
        errors.append(f"threat_guard import: {e}")
        print(f"❌ threat_guard: {e}")
    
    # Test 2: threat_hunter
    try:
        from agents.profiles.threat_hunter import ThreatHunter
        print("✅ threat_hunter: ThreatHunter class OK")
    except Exception as e:
        errors.append(f"threat_hunter import: {e}")
        print(f"❌ threat_hunter: {e}")
    
    # Test 3: army agent
    try:
        from agents.justice.army import ArmyAgent, SelfHealState, HardSafetyGate, army_command
        print(f"✅ army: ArmyAgent OK (monitoring {len(army_command.known_signatures)} files)")
        
        # Test hard-safety gate
        gate = army_command.check_hard_safety_gate(0.8, 0.6, True)
        print(f"   Hard-Safety Gate (Ψ=0.8, Ψ_indep=0.6): {'APPROVED' if gate else 'DENIED'}")
        
        gate2 = army_command.check_hard_safety_gate(0.3, 0.2, False)
        print(f"   Hard-Safety Gate (Ψ=0.3, Ψ_indep=0.2): {'APPROVED' if gate2 else 'DENIED'}")
        
        # Test defense report
        report = army_command.get_defense_report()
        print(f"   Defense Report: tau2={report['adaptive_threshold_tau2']}, reward={report['cumulative_reward']}")
        
        # Test patrol
        result = army_command.patrol_perimeter()
        print(f"   Patrol: {'SECURE' if result else 'COMPROMISED'}")
        
    except Exception as e:
        errors.append(f"army import: {e}")
        print(f"❌ army: {e}")
    
    # Test 4: cascade config
    try:
        from agents.safety.threat_scanner import CascadeConfig, UnifiedThreatPotential, ShieldScore
        
        cfg = CascadeConfig()
        utp = UnifiedThreatPotential(cfg)
        
        # Test Psi computation
        psi = utp.compute_psi(0.8, 0.6, 0.9, 0.5, 0.3)
        print(f"✅ Ψ(0.8, 0.6, 0.9, 0.5, 0.3) = {psi:.4f}")
        
        # Test action selection  
        action = utp.select_optimal_action(psi)
        print(f"   Optimal action for Ψ={psi:.4f}: {action.value}")
        
        # Test deep budget
        budget = utp.compute_deep_budget(0.5)
        print(f"   B_deep(0.5) = {budget:.4f}")
        
        # Test ShieldScore
        shield = ShieldScore(cfg)
        shield.record_scan(10.0, True, True)
        shield.record_scan(5.0, False, False)
        shield.record_scan(8.0, True, True)
        ss = shield.compute()
        print(f"   ShieldScore* = {ss:.4f}")
        
    except Exception as e:
        errors.append(f"cascade framework: {e}")
        print(f"❌ cascade framework: {e}")
    
    # Test 5: Full scan pipeline
    try:
        from agents.safety.threat_scanner import ThreatScanner
        
        scanner = ThreatScanner()
        
        # Scan this test file itself
        report = scanner.scan_file(__file__)
        print(f"✅ Full scan pipeline:")
        print(f"   Target: {report.target}")
        print(f"   Cascade Stage: {report.cascade_stage_reached}")
        print(f"   Stage Scores: {report.stage_scores}")
        print(f"   Ψ(x) = {report.psi_score:.4f}")
        print(f"   Is Threat: {report.is_threat}")
        print(f"   Action: {report.recommended_action.value}")
        print(f"   Latency: {report.scan_latency_ms:.2f}ms")
        
    except Exception as e:
        errors.append(f"full scan pipeline: {e}")
        print(f"❌ full scan pipeline: {e}")
    
    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("═" * 50)
        print("ALL VERIFICATION CHECKS PASSED ✅")
        print("═" * 50)
        return 0

if __name__ == "__main__":
    sys.exit(test_all())
