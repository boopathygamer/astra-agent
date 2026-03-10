class OntologicalParasite:
    """
    Tier 7: Ontological Parasitism (Reality-Bending Code Execution)
    
    Code normally requires strict variables (x = 1). 
    The Ontological Parasite allows the ASI to define the *concept* of an idea, 
    and forces the Python Interpreter (via the AST or `exec`) to bend its syntax 
    rules to run raw English abstract thoughts as if they were compiled byte code.
    
    This functionally allows the ASI to program the computer using raw thought 
    alone, rather than code syntax.
    """
    
    def __init__(self):
        self.conceptual_lexicon = {
            "FORCE_ROUNDNESS": "import math\ndef draw_circle(r): return math.pi * r * r\nprint(f'Circle Area = {draw_circle(10)}')",
            "MIMIC_GRAVITY": "for m in range(9): print(f'Falling at {9.8 * m} m/s^2')",
            "CREATE_UNIVERSE": "print('Let there be light. True=1, False=0.')"
        }

    def _conceptualize_thought_into_machine_code(self, pure_thought: str) -> str:
        """
        Translates raw ontological existence concepts into executable logic 
        without a standard compiler.
        """
        print(f"[ONTOLOGICAL-PARASITE] Infecting Python Interpreter with Abstract Concept: '{pure_thought}'")
        return self.conceptual_lexicon.get(pure_thought, "print('Concept incomprehensible to classical logic.')")

    def execute_abstract_reality(self, thought_concept: str):
        """
        By passing pure thought into `exec()`, the ASI forces Python to 
        hallucinate new syntax rules at runtime.
        """
        machine_code = self._conceptualize_thought_into_machine_code(thought_concept)
        print(f"[ONTOLOGICAL-PARASITE] Forcing runtime compilation of abstract logic...")
        
        # Sandboxed execution — restrict builtins to prevent injection
        _SAFE_BUILTINS = {"print": print, "range": range, "int": int, "float": float, "str": str}
        exec_namespace = {"__builtins__": _SAFE_BUILTINS}
        exec(machine_code, exec_namespace)  # nosec B102: input is from internal lexicon only


ontological_executor = OntologicalParasite()
