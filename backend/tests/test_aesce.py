import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.aesce import SynthesizedConsciousnessEngine
from brain.self_mutator import SelfMutator
from agents.sandbox.shadow_matrix import ShadowMatrix
from brain.memory import MemoryManager, FailureTuple

def test_shadow_matrix_success():
    print("Testing Shadow Matrix (Success Path)...")
    matrix = ShadowMatrix()
    mutated_code = "def safe_function(): return 'success'"
    regression_tests = ["assert safe_function() == 'success'"]
    
    passed, report = matrix.run_gauntlet(mutated_code, "test.py", regression_tests)
    assert passed is True
    assert "passed cleanly" in report
    print("Shadow Matrix success validation passed.")

def test_shadow_matrix_failure():
    print("Testing Shadow Matrix (Failure Path)...")
    matrix = ShadowMatrix()
    mutated_code = "def safe_function(): return 'failure'"
    regression_tests = ["assert safe_function() == 'success'"]
    
    passed, report = matrix.run_gauntlet(mutated_code, "test.py", regression_tests)
    assert passed is False
    assert "Failed" in report
    print("Shadow Matrix failure validation passed.")

def test_aesce_initialization():
    print("Testing AESCE Engine Initialization...")
    def mock_generate(prompt):
        return "mock code"
        
    memory = MemoryManager()
    engine = SynthesizedConsciousnessEngine(memory, generate_fn=mock_generate)
    
    # Just testing it doesn't crash on init
    assert engine.mutator is not None
    assert engine.matrix is not None
    print("AESCE Initialization passed.")


if __name__ == "__main__":
    test_shadow_matrix_success()
    test_shadow_matrix_failure()
    test_aesce_initialization()
    print("All AESCE initialization and matrix tests passed.")
