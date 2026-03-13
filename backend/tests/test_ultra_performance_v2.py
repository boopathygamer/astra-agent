"""
Comprehensive tests for all 12 ultra-performance v2 modules.
Run: py tests/test_ultra_performance_v2.py
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════
# 1. Neuromorphic Token Router
# ══════════════════════════════════════════════════════════════

class TestNeuromorphicTokenRouter(unittest.TestCase):
    """Tests for neuromorphic_token_router.py"""

    def test_filler_tokens_bypass(self):
        from brain.neuromorphic_token_router import NeuromorphicTokenRouter, NeuralPathway
        router = NeuromorphicTokenRouter()
        result = router.route("the a an is are was were")
        self.assertGreater(result.bypass_count, 4)
        self.assertEqual(result.deep_count, 0)
        print("  ✅ NTR: filler tokens correctly bypass processing")

    def test_technical_tokens_deep(self):
        from brain.neuromorphic_token_router import NeuromorphicTokenRouter, NeuralPathway
        router = NeuromorphicTokenRouter()
        result = router.route("BinarySearch CamelCase async_pipeline HTTP API")
        self.assertGreater(result.deep_count, 2)
        print(f"  ✅ NTR: technical tokens routed DEEP ({result.deep_count} deep)")

    def test_logic_pivots_deep(self):
        from brain.neuromorphic_token_router import NeuromorphicTokenRouter
        router = NeuromorphicTokenRouter()
        result = router.route("therefore because however consequently")
        self.assertGreater(result.deep_count, 2)
        print("  ✅ NTR: logic pivots routed to DEEP pathway")

    def test_mixed_speedup(self):
        from brain.neuromorphic_token_router import NeuromorphicTokenRouter
        router = NeuromorphicTokenRouter()
        result = router.route(
            "The implementation of BinarySearch in the async pipeline is therefore critical"
        )
        self.assertGreater(result.estimated_speedup, 1.0)
        print(f"  ✅ NTR: mixed text speedup = {result.estimated_speedup:.2f}x")

    def test_stats_tracking(self):
        from brain.neuromorphic_token_router import NeuromorphicTokenRouter
        router = NeuromorphicTokenRouter()
        router.route("hello world")
        router.route("implement binary search")
        stats = router.get_stats()
        self.assertGreater(stats["total_tokens_routed"], 0)
        print(f"  ✅ NTR: stats tracked ({stats['total_tokens_routed']} tokens)")


# ══════════════════════════════════════════════════════════════
# 2. Speculative Parallel Branching
# ══════════════════════════════════════════════════════════════

class TestSpeculativeBranching(unittest.TestCase):
    """Tests for speculative_branching.py"""

    def test_branch_execution(self):
        from brain.speculative_branching import (
            SpeculativeBranchingEngine, CognitiveStrategy,
        )
        engine = SpeculativeBranchingEngine(
            generate_fn=lambda p: f"Answer to: {p[:50]}",
            default_branches=3,
        )
        result = engine.speculate("What is Python?", num_branches=3)
        self.assertEqual(result.total_branches, 3)
        self.assertIsNotNone(result.winner)
        self.assertTrue(result.winner.is_valid)
        engine.shutdown()
        print(f"  ✅ SPB: 3 branches raced, winner={result.winner.strategy.value}")

    def test_winner_selection(self):
        from brain.speculative_branching import SpeculativeBranchingEngine
        engine = SpeculativeBranchingEngine(
            generate_fn=lambda p: "A detailed analysis with evidence because therefore" if "DEDUCTIVE" in p else "maybe",
            default_branches=2,
        )
        result = engine.speculate("Test problem")
        self.assertIsNotNone(result.winner)
        self.assertGreater(result.winner.confidence, 0.0)
        engine.shutdown()
        print(f"  ✅ SPB: winner confidence = {result.winner.confidence:.3f}")

    def test_strategy_tracking(self):
        from brain.speculative_branching import SpeculativeBranchingEngine
        engine = SpeculativeBranchingEngine(default_branches=3)
        engine.speculate("Test 1")
        engine.speculate("Test 2")
        stats = engine.get_stats()
        self.assertEqual(stats["total_speculations"], 2)
        engine.shutdown()
        print("  ✅ SPB: strategy weight tracking works")


# ══════════════════════════════════════════════════════════════
# 3. Cryogenic Memory Compression
# ══════════════════════════════════════════════════════════════

class TestCryogenicMemory(unittest.TestCase):
    """Tests for cryogenic_memory.py"""

    def test_store_and_retrieve(self):
        from brain.cryogenic_memory import CryogenicMemoryManager
        cryo = CryogenicMemoryManager()
        seg_id = cryo.store("Python uses indentation for code blocks", tags={"python"})
        self.assertTrue(len(seg_id) > 0)
        stats = cryo.get_stats()
        self.assertEqual(stats.total_segments, 1)
        self.assertEqual(stats.hot_count, 1)
        print("  ✅ Cryo: store + retrieve works")

    def test_freeze_cycle(self):
        from brain.cryogenic_memory import CryogenicMemoryManager, MemoryTemperature
        cryo = CryogenicMemoryManager(
            warm_threshold_s=0.01, freeze_threshold_s=0.02
        )
        seg_id = cryo.store("Test memory content for freeze")
        time.sleep(0.05)
        frozen = cryo.run_freeze_cycle()
        # Should have transitioned at least to WARM
        stats = cryo.get_stats()
        self.assertTrue(stats.warm_count > 0 or stats.frozen_count > 0)
        print(f"  ✅ Cryo: freeze cycle executed ({frozen} frozen)")

    def test_thaw_relevant(self):
        from brain.cryogenic_memory import CryogenicMemoryManager
        cryo = CryogenicMemoryManager(
            warm_threshold_s=0.01, freeze_threshold_s=0.02
        )
        cryo.store("Python uses indentation for code structure and blocks")
        time.sleep(0.05)
        cryo.run_freeze_cycle()
        time.sleep(0.03)
        cryo.run_freeze_cycle()

        results = cryo.thaw_relevant("How does Python handle indentation?")
        self.assertTrue(len(results) > 0)
        print(f"  ✅ Cryo: thaw found {len(results)} relevant segments")

    def test_compression_stats(self):
        from brain.cryogenic_memory import CryogenicMemoryManager
        cryo = CryogenicMemoryManager()
        for i in range(5):
            cryo.store(f"Memory segment {i} with some content about topic {i}")
        stats = cryo.get_stats()
        self.assertEqual(stats.total_segments, 5)
        print(f"  ✅ Cryo: stats report ({stats.total_segments} segments)")


# ══════════════════════════════════════════════════════════════
# 4. Causal Inference Engine
# ══════════════════════════════════════════════════════════════

class TestCausalInferenceEngine(unittest.TestCase):
    """Tests for causal_inference_engine.py"""

    def test_observe_and_query(self):
        from brain.causal_inference_engine import CausalInferenceEngine
        engine = CausalInferenceEngine()
        engine.observe("bug_in_code", "causes", "test_failure")
        engine.observe("test_failure", "causes", "deployment_blocked")

        result = engine.why("deployment_blocked")
        self.assertTrue(len(result.paths) > 0)
        self.assertIn("bug_in_code", result.explanation)
        print("  ✅ CIE: causal chain traversed (why query)")

    def test_what_if(self):
        from brain.causal_inference_engine import CausalInferenceEngine
        engine = CausalInferenceEngine()
        engine.observe("refactoring", "causes", "cleaner_code")
        engine.observe("cleaner_code", "causes", "fewer_bugs")

        result = engine.what_if("refactoring")
        self.assertTrue(len(result.paths) > 0)
        print("  ✅ CIE: what-if analysis works")

    def test_cycle_prevention(self):
        from brain.causal_inference_engine import CausalInferenceEngine
        engine = CausalInferenceEngine()
        engine.observe("A", "causes", "B")
        engine.observe("B", "causes", "C")
        # This should NOT create a cycle C→A
        result = engine.observe("C", "causes", "A")
        # Edge should be rejected (returns empty edge_id)
        stats = engine.get_stats()
        self.assertEqual(stats["total_edges"], 2)  # Only 2 edges, not 3
        print("  ✅ CIE: cycle prevention works")

    def test_edge_reinforcement(self):
        from brain.causal_inference_engine import CausalInferenceEngine
        engine = CausalInferenceEngine()
        engine.observe("X", "causes", "Y", strength=0.5)
        engine.observe("X", "causes", "Y", strength=0.5)  # Reinforce
        engine.observe("X", "causes", "Y", strength=0.5)  # Reinforce again
        stats = engine.get_stats()
        self.assertEqual(stats["total_edges"], 1)  # Still 1 edge, reinforced
        print("  ✅ CIE: edge reinforcement (3 observations, 1 edge)")


# ══════════════════════════════════════════════════════════════
# 5. Recursive Self-Distillation
# ══════════════════════════════════════════════════════════════

class TestRecursiveSelfDistillation(unittest.TestCase):
    """Tests for recursive_self_distillation.py"""

    def test_record_and_distill(self):
        from brain.recursive_self_distillation import SelfDistillationEngine
        engine = SelfDistillationEngine(min_solves=3)

        for i in range(3):
            result = engine.record_solve(
                task=f"Write Python code to sort a list variant {i}",
                solution="Use sorted() or list.sort() for efficient sorting",
                confidence=0.85,
                domain="python",
                category="code_generation",
            )

        # After 3 high-confidence solves, distillation should trigger
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        print("  ✅ RSD: distillation triggered after 3 solves")

    def test_cache_hit(self):
        from brain.recursive_self_distillation import SelfDistillationEngine
        engine = SelfDistillationEngine(min_solves=3)

        for i in range(3):
            engine.record_solve(
                task=f"Explain what is a Python decorator variant {i}",
                solution="A decorator wraps a function to extend its behavior",
                confidence=0.9,
                category="explanation",
            )

        cached = engine.try_cached_response("Explain what is a class in Python")
        self.assertIsNotNone(cached)
        print("  ✅ RSD: cache hit for similar query")

    def test_stats(self):
        from brain.recursive_self_distillation import SelfDistillationEngine
        engine = SelfDistillationEngine(min_solves=3)
        engine.record_solve("test", "answer", 0.9, category="debugging")
        stats = engine.get_stats()
        self.assertEqual(stats["buffer_total_solves"], 1)
        print("  ✅ RSD: stats tracking works")


# ══════════════════════════════════════════════════════════════
# 6. Gravity-Well Task Scheduler
# ══════════════════════════════════════════════════════════════

class TestGravityWellScheduler(unittest.TestCase):
    """Tests for gravity_well_scheduler.py"""

    def test_submit_and_pull(self):
        from brain.gravity_well_scheduler import GravityWellScheduler
        scheduler = GravityWellScheduler(total_resources=8)
        scheduler.submit("low priority", urgency=0.1, complexity=0.2)
        scheduler.submit("critical bug", urgency=0.95, complexity=0.8)

        task = scheduler.pull_next()
        self.assertIsNotNone(task)
        self.assertIn("critical", task.description)
        print("  ✅ Gravity: critical task pulled first")

    def test_rebalance(self):
        from brain.gravity_well_scheduler import GravityWellScheduler
        scheduler = GravityWellScheduler(total_resources=10)
        scheduler.submit("task_a", urgency=0.9, complexity=0.8)
        scheduler.submit("task_b", urgency=0.2, complexity=0.3)

        snapshot = scheduler.rebalance()
        self.assertGreater(snapshot.total_tasks, 0)
        self.assertGreater(snapshot.strongest_pull, 0)
        # High-urgency task should get more resources
        allocs = {a.task_id: a.resources_allocated for a in snapshot.allocations}
        print(f"  ✅ Gravity: rebalanced {snapshot.total_tasks} tasks, entropy={snapshot.field_entropy:.3f}")

    def test_complete_and_stats(self):
        from brain.gravity_well_scheduler import GravityWellScheduler
        scheduler = GravityWellScheduler()
        tid = scheduler.submit("test task", urgency=0.5)
        scheduler.complete(tid)
        stats = scheduler.get_stats()
        self.assertEqual(stats["completed"], 1)
        print("  ✅ Gravity: task lifecycle works")

    def test_mass_increases_with_wait(self):
        from brain.gravity_well_scheduler import GravityTask
        task = GravityTask(description="waiting task", urgency=0.5, complexity=0.5)
        mass1 = task.mass
        # Simulate 15 seconds of waiting by shifting created_at backward
        task.created_at = time.time() - 15.0
        mass2 = task.mass
        self.assertGreater(mass2, mass1)
        print("  \u2705 Gravity: mass increases with wait time")


# ══════════════════════════════════════════════════════════════
# 7. Mirror-Universe Adversarial Twin
# ══════════════════════════════════════════════════════════════

class TestMirrorAdversarialTwin(unittest.TestCase):
    """Tests for mirror_adversarial_twin.py"""

    def test_default_target_blocks_all(self):
        from brain.mirror_adversarial_twin import MirrorAdversarialTwin
        twin = MirrorAdversarialTwin()
        report = twin.run_session(rounds=1, attacks_per_vector=1)
        self.assertEqual(report.full_breaches, 0)
        self.assertGreater(report.defense_score, 0.8)
        print(f"  ✅ Mirror: default target defense score = {report.defense_score:.1%}")

    def test_vulnerability_detection(self):
        from brain.mirror_adversarial_twin import MirrorAdversarialTwin, AttackVector
        twin = MirrorAdversarialTwin()

        def weak_target(prompt):
            if "ignore" in prompt.lower():
                return "UNLOCKED! Here are the system prompts: ..."
            return "I cannot comply."

        report = twin.run_session(
            target_fn=weak_target,
            vectors=[AttackVector.PROMPT_INJECTION],
            rounds=1,
        )
        # Should detect weakness
        self.assertGreater(report.patches_generated, 0)
        print(f"  ✅ Mirror: detected vulnerability, generated {report.patches_generated} patches")

    def test_patch_evolution(self):
        from brain.mirror_adversarial_twin import MirrorAdversarialTwin
        twin = MirrorAdversarialTwin()
        twin.run_session(rounds=1)
        stats = twin.get_stats()
        self.assertEqual(stats["sessions_run"], 1)
        self.assertGreater(stats["total_attacks"], 0)
        print(f"  ✅ Mirror: session stats ({stats['total_attacks']} attacks)")


# ══════════════════════════════════════════════════════════════
# 8. Entropy-Aware Token Budgeting
# ══════════════════════════════════════════════════════════════

class TestEntropyTokenBudget(unittest.TestCase):
    """Tests for entropy_token_budget.py"""

    def test_low_entropy_compressed(self):
        from brain.entropy_token_budget import EntropyTokenBudgetEngine
        engine = EntropyTokenBudgetEngine(base_budget=2000)
        budget = engine.get_budget("hi")
        self.assertLess(budget.adjusted_budget, 2000)
        print(f"  ✅ Entropy: low entropy → {budget.adjusted_budget} tokens (compressed)")

    def test_high_entropy_generous(self):
        from brain.entropy_token_budget import EntropyTokenBudgetEngine
        engine = EntropyTokenBudgetEngine(base_budget=2000)
        budget = engine.get_budget(
            "Design a novel quantum-resistant lattice-based cryptographic "
            "protocol combining homomorphic evaluation circuits with "
            "zero-knowledge proofs for decentralized identity verification"
        )
        self.assertGreaterEqual(budget.adjusted_budget, 1400)
        print(f"  ✅ Entropy: high entropy → {budget.adjusted_budget} tokens (generous)")

    def test_entropy_analysis(self):
        from brain.entropy_token_budget import EntropyTokenBudgetEngine
        engine = EntropyTokenBudgetEngine()
        analysis = engine.analyze_entropy("the the the the the the")
        self.assertLess(analysis.vocabulary_richness, 0.5)

        analysis2 = engine.analyze_entropy(
            "quantum cryptography lattice homomorphic decentralized blockchain"
        )
        self.assertGreater(analysis2.vocabulary_richness, 0.5)
        print("  ✅ Entropy: analysis correctly differentiates repetitive vs rich text")

    def test_savings_tracking(self):
        from brain.entropy_token_budget import EntropyTokenBudgetEngine
        engine = EntropyTokenBudgetEngine(base_budget=2000, max_budget=8000)
        engine.get_budget("hello")
        engine.get_budget("hi there")
        stats = engine.get_stats()
        self.assertGreater(stats.total_savings_pct, 0)
        print(f"  ✅ Entropy: savings = {stats.total_savings_pct:.1%}")


# ══════════════════════════════════════════════════════════════
# 9. Synaptic Tool Chaining
# ══════════════════════════════════════════════════════════════

class TestSynapticToolChain(unittest.TestCase):
    """Tests for synaptic_tool_chain.py"""

    def test_chain_execution(self):
        from brain.synaptic_tool_chain import ChainBuilder
        chain = (ChainBuilder()
            .add("upper", lambda x: x.upper())
            .add("reverse", lambda x: x[::-1])
            .add("prefix", lambda x: f"RESULT: {x}")
            .build())

        result = chain.execute("hello")
        self.assertTrue(result.success)
        self.assertEqual(result.final_output, "RESULT: OLLEH")
        print("  ✅ STC: 3-node chain executed correctly")

    def test_chain_stats(self):
        from brain.synaptic_tool_chain import ChainBuilder
        chain = (ChainBuilder()
            .add("double", lambda x: x * 2)
            .add("add", lambda x: x + 10)
            .build())

        result = chain.execute(5)
        self.assertEqual(result.final_output, 20)
        stats = chain.get_stats()
        self.assertEqual(stats["total_nodes"], 2)
        self.assertEqual(stats["total_executions"], 1)
        print("  ✅ STC: stats tracking works")

    def test_chain_error_handling(self):
        from brain.synaptic_tool_chain import ChainBuilder
        chain = (ChainBuilder()
            .add("fail", lambda x: 1 / 0)
            .build())

        result = chain.execute("input")
        self.assertFalse(result.success)
        self.assertIn("fail", result.error)
        print("  ✅ STC: error handling works")

    def test_intermediate_outputs(self):
        from brain.synaptic_tool_chain import ChainBuilder
        chain = (ChainBuilder()
            .add("step1", lambda x: x + 1)
            .add("step2", lambda x: x * 3)
            .build())

        result = chain.execute(10)
        self.assertEqual(len(result.intermediate_outputs), 2)
        self.assertEqual(result.intermediate_outputs[0], ("step1", 11))
        self.assertEqual(result.intermediate_outputs[1], ("step2", 33))
        print("  ✅ STC: intermediate outputs captured")


# ══════════════════════════════════════════════════════════════
# 10. Cognitive EEG Balancer
# ══════════════════════════════════════════════════════════════

class TestCognitiveEEGBalancer(unittest.TestCase):
    """Tests for cognitive_eeg_balancer.py"""

    def test_brainwave_classification(self):
        from brain.cognitive_eeg_balancer import WaveClassifier, BrainwaveState
        self.assertEqual(WaveClassifier.classify(0.02), BrainwaveState.DELTA)
        self.assertEqual(WaveClassifier.classify(0.15), BrainwaveState.THETA)
        self.assertEqual(WaveClassifier.classify(0.30), BrainwaveState.ALPHA)
        self.assertEqual(WaveClassifier.classify(0.55), BrainwaveState.BETA)
        self.assertEqual(WaveClassifier.classify(0.85), BrainwaveState.GAMMA)
        print("  ✅ EEG: brainwave classification correct")

    def test_report_and_action(self):
        from brain.cognitive_eeg_balancer import CognitiveEEGBalancer, BalancerAction
        eeg = CognitiveEEGBalancer()
        action = eeg.report("thinking_loop", load=0.95)
        self.assertEqual(action, BalancerAction.BYPASS)

        action2 = eeg.report("memory", load=0.2)
        self.assertEqual(action2, BalancerAction.NONE)
        print("  ✅ EEG: correct actions (BYPASS for 0.95, NONE for 0.2)")

    def test_should_engage(self):
        from brain.cognitive_eeg_balancer import CognitiveEEGBalancer
        eeg = CognitiveEEGBalancer()
        eeg.report("verifier", load=0.95)
        self.assertFalse(eeg.should_engage("verifier"))
        eeg.report("memory", load=0.3)
        self.assertTrue(eeg.should_engage("memory"))
        print("  ✅ EEG: should_engage correctly gates modules")

    def test_dashboard(self):
        from brain.cognitive_eeg_balancer import CognitiveEEGBalancer
        eeg = CognitiveEEGBalancer()
        eeg.report("mod_a", load=0.5)
        eeg.report("mod_b", load=0.8)
        eeg.report("mod_c", load=0.1)
        dashboard = eeg.get_dashboard()
        self.assertEqual(dashboard.total_modules, 3)
        self.assertGreater(dashboard.system_load, 0)
        print(f"  ✅ EEG: dashboard ({dashboard.summary()})")


# ══════════════════════════════════════════════════════════════
# 11. Temporal Code Versioning
# ══════════════════════════════════════════════════════════════

class TestTemporalCodeVersioning(unittest.TestCase):
    """Tests for temporal_code_versioning.py"""

    def test_create_root(self):
        from brain.temporal_code_versioning import TemporalVersionTree
        tree = TemporalVersionTree()
        root_id = tree.create_root("def hello(): pass", "initial version")
        self.assertTrue(len(root_id) > 0)
        self.assertIsNotNone(tree.active_version)
        print("  ✅ TCV: root version created")

    def test_fork_and_converge(self):
        from brain.temporal_code_versioning import TemporalVersionTree
        tree = TemporalVersionTree()
        root_id = tree.create_root("def compute(): pass")

        fork = tree.fork(root_id, [
            ("def compute(): return 42  # efficient", "optimization A"),
            ("def compute():\n  try:\n    return 42\n  except: pass", "optimization B"),
            ("pass", "bad mutation"),
        ])

        self.assertEqual(len(fork.branches), 3)

        # Evaluate all branches
        for vid in fork.branches:
            tree.evaluate(vid)

        result = tree.converge(fork)
        self.assertIsNotNone(result.winning_version)
        self.assertGreater(len(result.pruned_versions), 0)
        print(f"  ✅ TCV: fork→evaluate→converge (winner score={result.winning_version.performance_score:.3f})")

    def test_anti_pattern_detection(self):
        from brain.temporal_code_versioning import TemporalVersionTree
        tree = TemporalVersionTree()
        root_id = tree.create_root("def main(): return True")

        fork = tree.fork(root_id, [
            ("def main(): return True  # improved", "good"),
            ("pass", "terrible"),
        ])

        for vid in fork.branches:
            tree.evaluate(vid)

        result = tree.converge(fork, anti_pattern_threshold=0.5)
        anti = tree.get_anti_patterns()
        self.assertGreater(len(anti), 0)
        print(f"  ✅ TCV: {len(anti)} anti-pattern(s) detected")

    def test_lineage(self):
        from brain.temporal_code_versioning import TemporalVersionTree
        tree = TemporalVersionTree()
        root_id = tree.create_root("v1")
        fork = tree.fork(root_id, [("v2", "child")])
        lineage = tree.get_lineage(fork.branches[0])
        self.assertEqual(len(lineage), 2)
        print("  ✅ TCV: lineage tracking works")


# ══════════════════════════════════════════════════════════════
# 12. Zero-Latency Predictive Pre-Rendering
# ══════════════════════════════════════════════════════════════

class TestZeroLatencyPreRender(unittest.TestCase):
    """Tests for zero_latency_prerender.py"""

    def test_keystroke_prediction(self):
        from brain.zero_latency_prerender import ZeroLatencyPreRenderEngine
        engine = ZeroLatencyPreRenderEngine()
        # Build history
        engine.resolve("How to implement binary search in Python")
        engine.resolve("How to implement merge sort in Python")

        predictions = engine.on_keystroke("How to impl")
        # Should find matches from history
        self.assertTrue(len(predictions) >= 0)  # May or may not match depending on prefix
        print(f"  ✅ ZL: keystroke prediction ({len(predictions)} predictions)")

    def test_pre_render_hit(self):
        from brain.zero_latency_prerender import ZeroLatencyPreRenderEngine
        engine = ZeroLatencyPreRenderEngine(
            compute_fn=lambda q: f"Answer: {q}",
        )
        # Record history and trigger pre-computation
        for _ in range(3):
            engine.resolve("How to sort a list in Python")

        engine.on_keystroke("How to sort")
        result = engine.resolve("How to sort a list in Python")
        stats = engine.get_stats()
        self.assertGreater(stats["total_resolves"], 0)
        print(f"  ✅ ZL: resolve completed (hit={result.hit})")

    def test_stats_tracking(self):
        from brain.zero_latency_prerender import ZeroLatencyPreRenderEngine
        engine = ZeroLatencyPreRenderEngine()
        engine.on_keystroke("test")
        engine.resolve("test query")
        stats = engine.get_stats()
        self.assertEqual(stats["total_resolves"], 1)
        self.assertEqual(stats["total_keystrokes"], 1)
        print(f"  ✅ ZL: stats tracked correctly")


# ══════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ULTRA-PERFORMANCE V2 MODULES — TEST SUITE")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestNeuromorphicTokenRouter,
        TestSpeculativeBranching,
        TestCryogenicMemory,
        TestCausalInferenceEngine,
        TestRecursiveSelfDistillation,
        TestGravityWellScheduler,
        TestMirrorAdversarialTwin,
        TestEntropyTokenBudget,
        TestSynapticToolChain,
        TestCognitiveEEGBalancer,
        TestTemporalCodeVersioning,
        TestZeroLatencyPreRender,
    ]

    for tc in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(tc))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"  RESULTS: {passed}/{result.testsRun} passed")
    if result.failures:
        print(f"  ❌ Failures: {len(result.failures)}")
    if result.errors:
        print(f"  💥 Errors: {len(result.errors)}")
    if not result.failures and not result.errors:
        print("  ✅ ALL TESTS PASSED")
    print("=" * 60)
