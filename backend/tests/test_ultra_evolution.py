"""
Basic verification tests for the 5 advanced ASI Evolution features.
These tests verify that the classes can be instantiated and basic non-LLM logic works.
"""

import sys
import os
import asyncio

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.telepathic_ui import TelepathicWatcherInjector
from brain.omni_physics_engine import MultiverseSimulator

def test_telepathic_ui():
    print("Testing Telepathic UI Injection...")
    mock_html = "<html><body><h1>Test</h1></body>"
    result = TelepathicWatcherInjector.inject_watcher(mock_html)
    assert "[ASI TELEPATHY]" in result
    print("Telepathic UI test passed.\n")
    
def test_multiverse_simulator():
    print("Testing Multiverse Simulator...")
    # Mock vulnerable code
    mock_code = "while True:\n    sql = 'SELECT * FROM users WHERE name=' + request.name"
    result = MultiverseSimulator.simulate_quantum_failures(mock_code)
    
    # Check that failures were caught
    assert len(result["catastrophes_averted"]) > 0
    print("Multiverse Simulator test passed.\n")

if __name__ == "__main__":
    print("--- Running ASI Tier Verification Tests ---")
    
    try:
        from agents.code_arena import GeneticCodeArena
        from agents.profit_compiler import ProfitCompiler
        from agents.sentient_npc_engine import SentientNPCOrchestrator
        print("Imports successful for LLM-driven agents.")
    except Exception as e:
        print(f"Import failed: {e}")
        
    test_telepathic_ui()
    test_multiverse_simulator()
    
    print("All static tests passed. LLM agents require API keys to run full simulations.")
