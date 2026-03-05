import traceback
import sys
sys.path.insert(0, r'c:\super-agent\backend')

try:
    from brain.aesce import SynthesizedConsciousnessEngine
except Exception:
    with open(r'c:\super-agent\trace.txt', 'w') as f:
        f.write(traceback.format_exc())
