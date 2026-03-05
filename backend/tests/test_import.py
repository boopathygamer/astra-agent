import traceback
import sys
sys.path.insert(0, r'c:\super-agent\backend')

try:
    from brain.aesce import SynthesizedConsciousnessEngine
    print("Success")
except Exception:
    traceback.print_exc()
