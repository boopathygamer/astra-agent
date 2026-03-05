import sys
import logging
from core.model_providers import ProviderRegistry
from brain.expert_reflection import ExpertReflectionEngine

logging.basicConfig(level=logging.INFO, format="%(message)s")

def run_domain_tests():
    with open("expert_results.txt", "w", encoding="utf-8") as f:
        f.write("============================================================\n")
        f.write("  🧠 Testing Cross-Domain First Principle Extraction\n")
        f.write("============================================================\n\n")
        
        # Mock the LLM provider for testing without an API key
        def mock_generate_fn(prompt: str, **kwargs) -> str:
            if "escape velocity" in prompt:
                return '{"root_insight": "Energy conservation principles bridge conservative fields with non-conservative work terms.", "actionable_rule": "Always formulate the total energy state equation before attempting kinematic isolation."}'
            elif "infinitely many prime" in prompt:
                return '{"root_insight": "Topological compactness connects discrete number properties with continuous spatial concepts.", "actionable_rule": "Map discrete arithmetic progression logic onto topological spaces to prove infinitude."}'
            elif "Byzantine Generals" in prompt:
                return '{"root_insight": "Asynchronous consensus is mathematically bounded by the impossibility of deterministic failure detection.", "actionable_rule": "Enforce partial network synchrony assumptions when designing robust distributed consensus protocols."}'
            elif "longest palindromic" in prompt:
                return '{"root_insight": "Mirrored subproblem state logic linearly collapses quadratic boundary expansions.", "actionable_rule": "Store mirrored right-bound lengths in an array to prevent redundant palindrome center expansions."}'
            return '{}'
            
        generate_fn = mock_generate_fn
        reflection_engine = ExpertReflectionEngine(generate_fn)
    
        test_cases = [
            {
                "domain": "Physics",
                "problem": "Calculate the escape velocity of a projectile launched from a planet with mass M and radius R, factoring in a dense atmospheric drag variable.",
                "solution": "By setting the initial kinetic energy plus the integral of the drag work equal to the gravitational potential energy at the surface, we isolate v. We must use the work-energy theorem to account for the non-conservative drag force mathematically before solving the quadratic dependency."
            },
            {
                "domain": "Mathematics",
                "problem": "Prove that there are infinitely many prime numbers using a topological approach.",
                "solution": "We define a topology on the integers using arithmetic progressions as a basis. Since any arithmetic progression is both open and closed, and the union of all progressions pZ (where p is prime) is Z\\{-1, 1}, if there were finitely many primes, this union would be closed, making {-1, 1} open, which is impossible. Thus, infinite primes exist."
            },
            {
                "domain": "Logic Building",
                "problem": "Solve the Byzantine Generals Problem in an asynchronous network without cryptography.",
                "solution": "It is mathematically proven that in a purely asynchronous network without cryptographic signatures, a deterministic solution to the Byzantine Generals Problem is impossible if even one node can fail, due to the FLP impossibility result. We must introduce partial synchrony or randomized consensus algorithms."
            },
            {
                "domain": "Coding",
                "problem": "Optimize a Python function that finds the longest palindromic substring in a string of length N.",
                "solution": "Instead of expanding around the center in O(N^2) time, I implemented Manacher's Algorithm. By inserting dummy characters between every letter to handle even length palindromes, and maintaining a 'center' and 'right' boundary to reuse previously computed palindrome lengths via mirrored indices, the time complexity is reduced strictly to O(N)."
            }
        ]
        
        for case in test_cases:
            f.write(f"[{case['domain'].upper()}] Evaluating...\n")
            f.write(f"Problem: {case['problem'][:100]}...\n")
            principle = reflection_engine.extract_first_principle(
                problem=case["problem"],
                successful_solution=case["solution"],
                domain=case["domain"].lower()
            )
            
            if principle:
                f.write(f"💎 Extracted Axiom: {principle.actionable_rule}\n")
                f.write(f"🔬 Root Insight: {principle.root_insight}\n\n")
            else:
                f.write("❌ Failed to extract principle.\n\n")
            
if __name__ == "__main__":
    run_domain_tests()
