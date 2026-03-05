"""
Test script for Deep Expert Reflection.
Forces the brain to solve a complex math/logic puzzle requiring reasoning.
"""
import logging
from main import create_provider_registry
from agents.controller import AgentController
from brain.thinking_loop import ThinkingLoop

logging.basicConfig(level=logging.INFO)

def main():
    print("🧠 Booting Neural Network...")
    registry = create_provider_registry("auto")
    AgentController(registry.generate_fn())
    loop = ThinkingLoop(generate_fn=registry.generate_fn())
    
    puzzle = (
        "I have a 3-gallon jug and a 5-gallon jug. I need to measure exactly 4 gallons of water. "
        "Write out the exact sequence of steps to achieve this. Treat this as a logic programming problem."
    )
    
    print("\n🚀 Injecting Complex Problem into Thinking Loop...")
    result = loop.think(puzzle)
    
    print("\n" + "=" * 50)
    print("FINAL CONFIDENCE:", result.final_confidence)
    print("ITERATIONS SPENT:", result.iterations)
    print("FINAL ANSWER:\n", result.final_answer)

if __name__ == "__main__":
    main()
