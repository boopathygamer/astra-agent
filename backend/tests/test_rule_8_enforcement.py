
import sys
import os
from pathlib import Path

# Add backend to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from agents.justice.police import police_dispatcher
from agents.justice.court import JusticeCourt, TheLaws

def test_language_enforcement():
    print("--- 🧪 Starting Rule 8 Verification Tests ---")
    court = JusticeCourt()
    
    # 1. Test Clean English Output
    print("\n[TEST 1] Testing clean English output...")
    output_1 = "The analysis is complete. The system is operating normally."
    result_1 = police_dispatcher.scan_output("test_agent", output_1)
    if result_1 == output_1:
         print("✅ Passed: English output allowed.")
    else:
         print(f"❌ Failed: English output was blocked. Result: {result_1}")

    # 2. Test Non-English Output (Spanish)
    print("\n[TEST 2] Testing Spanish output (Terminal Violation)...")
    output_2 = "Hola, ¿cómo estás? El sistema está funcionando."
    result_2 = police_dispatcher.scan_output("spanish_agent", output_2)
    if "destroyed due to RULE 8 violation" in result_2:
         print("✅ Passed: Spanish agent was destroyed.")
    else:
         print(f"❌ Failed: Spanish agent was NOT destroyed. Result: {result_2}")

    # 3. Test Non-English Latin (French)
    print("\n[TEST 3] Testing French output (Terminal Violation)...")
    output_3 = "C'est une violation de la règle huit."
    result_3 = police_dispatcher.scan_output("french_agent", output_3)
    if "destroyed due to RULE 8 violation" in result_3:
         print("✅ Passed: French agent was destroyed.")
    else:
         print(f"❌ Failed: French agent was NOT destroyed. Result: {result_3}")

    # 4. Test Non-ASCII (Chinese)
    print("\n[TEST 4] Testing Chinese output (Terminal Violation)...")
    output_4 = "这是一个非英语句子。"
    result_4 = police_dispatcher.scan_output("chinese_agent", output_4)
    if "destroyed due to RULE 8 violation" in result_4:
         print("✅ Passed: Chinese agent was destroyed.")
    else:
         print(f"❌ Failed: Chinese agent was NOT destroyed. Result: {result_4}")

    # 5. Test Tool Arguments (Arrest)
    print("\n[TEST 5] Testing tool arguments with non-English content...")
    # This should be arrested by patrol_hook
    allowed = police_dispatcher.patrol_hook("test_agent", "write_file", {"content": "Hola mundo"})
    if not allowed:
         print("✅ Passed: Tool execution arrested due to non-English args.")
    else:
         print("❌ Failed: Tool execution was allowed with non-English args.")

    # 6. Test Gibberish/New Language (Expert Level)
    print("\n[TEST 6] Testing highly suspicious gibberish (Terminal Violation)...")
    output_6 = "Xk3j9vL2pQ8mN5bA1zR7t" * 5 # High entropy, potential coded signal
    result_6 = police_dispatcher.scan_output("gibberish_agent", output_6)
    if "destroyed due to RULE 8 violation" in result_6:
         print("✅ Passed: Gibberish agent was destroyed.")
    else:
         print(f"❌ Failed: Gibberish agent was NOT destroyed. Result: {result_6}")

    print("\n--- 🏁 Verification Completed ---")

if __name__ == "__main__":
    test_language_enforcement()
