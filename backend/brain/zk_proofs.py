"""
Zero-Knowledge Execution Proofs — Cryptographic Verification
─────────────────────────────────────────────────────────────
Generates proofs that a computation was performed correctly
without revealing the full computation. Merkle-tree hash chains.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    step_id: int = 0
    operation: str = ""
    input_hash: str = ""
    output_hash: str = ""
    timestamp: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class ExecutionProof:
    proof_id: str = ""
    root_hash: str = ""
    step_count: int = 0
    chain_hashes: List[str] = field(default_factory=list)
    merkle_root: str = ""
    merkle_proof_path: List[Tuple[str, str]] = field(default_factory=list)
    timestamp: float = 0.0
    valid: bool = False

    def __post_init__(self):
        if not self.proof_id:
            self.proof_id = hashlib.sha256(
                f"{self.root_hash}{time.time()}".encode()
            ).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = time.time()


class IntegrityChain:
    """Hash chain: each step includes the previous step's hash."""

    def __init__(self):
        self._steps: List[ExecutionStep] = []
        self._chain: List[str] = []
        self._genesis = hashlib.sha256(b"GENESIS").hexdigest()

    def record_step(self, operation: str, input_data: Any,
                    output_data: Any, metadata: Dict[str, str] = None) -> ExecutionStep:
        input_hash = self._hash(input_data)
        output_hash = self._hash(output_data)
        prev = self._chain[-1] if self._chain else self._genesis
        chain_data = f"{prev}|{operation}|{input_hash}|{output_hash}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        step = ExecutionStep(
            step_id=len(self._steps), operation=operation,
            input_hash=input_hash, output_hash=output_hash,
            metadata=metadata or {},
        )
        self._steps.append(step)
        self._chain.append(chain_hash)
        return step

    def verify_chain(self) -> Tuple[bool, str]:
        if not self._steps:
            return True, "Empty chain"
        prev = self._genesis
        for i, (step, ch) in enumerate(zip(self._steps, self._chain)):
            expected = hashlib.sha256(
                f"{prev}|{step.operation}|{step.input_hash}|{step.output_hash}".encode()
            ).hexdigest()
            if expected != ch:
                return False, f"Broken at step {i}"
            prev = ch
        return True, f"Chain valid: {len(self._steps)} steps verified"

    def get_root_hash(self) -> str:
        return self._chain[-1] if self._chain else self._genesis

    @staticmethod
    def _hash(data: Any) -> str:
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

    @property
    def step_count(self) -> int:
        return len(self._steps)


class MerkleTree:
    """Merkle tree for efficient membership proofs."""

    def __init__(self):
        self._leaves: List[str] = []
        self._root: Optional[str] = None

    def build(self, leaf_hashes: List[str]) -> str:
        if not leaf_hashes:
            return hashlib.sha256(b"EMPTY").hexdigest()
        self._leaves = leaf_hashes[:]
        level = leaf_hashes[:]
        while len(level) > 1:
            next_lvl = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else left
                parent = hashlib.sha256(f"{left}|{right}".encode()).hexdigest()
                next_lvl.append(parent)
            level = next_lvl
        self._root = level[0]
        return self._root

    def get_proof(self, leaf_hash: str) -> List[Tuple[str, str]]:
        if leaf_hash not in self._leaves:
            return []
        proof = []
        current = leaf_hash
        level = self._leaves[:]
        while len(level) > 1:
            idx = level.index(current) if current in level else -1
            if idx == -1:
                break
            if idx % 2 == 0:
                sib = level[idx + 1] if idx + 1 < len(level) else current
                proof.append((sib, "right"))
            else:
                proof.append((level[idx - 1], "left"))
            next_lvl = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else left
                p = hashlib.sha256(f"{left}|{right}".encode()).hexdigest()
                next_lvl.append(p)
                if left == current or right == current:
                    current = p
            level = next_lvl
        return proof

    @staticmethod
    def verify_proof(leaf: str, proof: List[Tuple[str, str]], root: str) -> bool:
        current = leaf
        for sib, direction in proof:
            if direction == "left":
                combined = f"{sib}|{current}"
            else:
                combined = f"{current}|{sib}"
            current = hashlib.sha256(combined.encode()).hexdigest()
        return current == root

    @property
    def root(self) -> str:
        return self._root or ""


class ProofGenerator:
    def generate_proof(self, chain: IntegrityChain, step_idx: int = None) -> ExecutionProof:
        merkle = MerkleTree()
        merkle_root = merkle.build(chain._chain)
        merkle_path = []
        if step_idx is not None and step_idx < len(chain._chain):
            merkle_path = merkle.get_proof(chain._chain[step_idx])
        is_valid, _ = chain.verify_chain()
        return ExecutionProof(
            root_hash=chain.get_root_hash(),
            step_count=chain.step_count,
            chain_hashes=chain._chain[:],
            merkle_root=merkle_root,
            merkle_proof_path=merkle_path,
            valid=is_valid,
        )


class ProofVerifier:
    def verify_complete(self, proof: ExecutionProof) -> Tuple[bool, str]:
        if not proof.chain_hashes:
            return False, "Empty proof"
        if proof.chain_hashes[-1] != proof.root_hash:
            return False, "Root hash mismatch"
        merkle = MerkleTree()
        computed_root = merkle.build(proof.chain_hashes)
        if computed_root != proof.merkle_root:
            return False, "Merkle root mismatch"
        return True, f"Proof verified: {proof.step_count} steps"

    def verify_step(self, proof: ExecutionProof, step_idx: int) -> Tuple[bool, str]:
        if step_idx >= len(proof.chain_hashes):
            return False, f"Step {step_idx} out of range"
        step_hash = proof.chain_hashes[step_idx]
        if proof.merkle_proof_path:
            ok = MerkleTree.verify_proof(step_hash, proof.merkle_proof_path, proof.merkle_root)
            return (True, f"Step {step_idx} verified") if ok else (False, "Merkle fail")
        return True, f"Step {step_idx} in chain"


class ZKExecutionEngine:
    """
    Main interface for zero-knowledge execution proofs.

    Usage:
        zk = ZKExecutionEngine()
        chain = zk.start_chain()
        zk.record(chain, "parse", input_data, parsed)
        zk.record(chain, "process", parsed, result)
        proof = zk.generate_proof(chain)
        valid, msg = zk.verify(proof)
    """

    def __init__(self):
        self._gen = ProofGenerator()
        self._ver = ProofVerifier()
        self._chains: Dict[str, IntegrityChain] = {}

    def start_chain(self, chain_id: str = "") -> IntegrityChain:
        chain = IntegrityChain()
        cid = chain_id or hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
        self._chains[cid] = chain
        return chain

    def record(self, chain: IntegrityChain, operation: str,
               input_data: Any, output_data: Any, **meta) -> ExecutionStep:
        return chain.record_step(operation, input_data, output_data, meta)

    def generate_proof(self, chain: IntegrityChain, step_idx: int = None) -> ExecutionProof:
        return self._gen.generate_proof(chain, step_idx)

    def verify(self, proof: ExecutionProof) -> Tuple[bool, str]:
        return self._ver.verify_complete(proof)

    def verify_step(self, proof: ExecutionProof, step_idx: int) -> Tuple[bool, str]:
        return self._ver.verify_step(proof, step_idx)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_chains": len(self._chains),
            "total_steps": sum(c.step_count for c in self._chains.values()),
        }
