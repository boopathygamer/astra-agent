import logging
import time
import threading
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class AirLLMEngine:
    """
    Astra Agent: Deep Thought Engine (AirLLM Wrapper)
    
    This engine uses `airllm` to load massive, state-of-the-art models (like 70B+ parameters) 
    that normally require multiple A100 GPUs onto consumer hardware (single 8GB GPU). It
    achieves this by swapping layers in and out of VRAM dynamically.
    
    WARNING: Inference is significantly slower than standard APIs due to PCI-e bandwidth,
    but it ensures 100% data privacy and unlocks "Impossible" local models for fleet learning.
    """
    
    def __init__(self, model_id: str = "garage-bAInd/Platypus2-70B-instruct"):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        self._load_lock = threading.Lock()  # Thread-safe initialization
        
    def load(self):
        """Lazy load the AirLLM model into memory (swapped layer mode)."""
        if self.is_loaded:
            return
        
        with self._load_lock:
            # Double-check after acquiring lock (another thread may have loaded)
            if self.is_loaded:
                return
            
        try:
            logger.info(f"[Deep Thought] Initializing AirLLM using HuggingFace ID: {self.model_id}")
            logger.info("[Deep Thought] This will use aggressive VRAM swapping. Downloading/Loading may take several minutes...")
            
            # Importing here to prevent main.py from crashing if airllm isn't installed
            from airllm import AutoModel
            
            # Initialize with layered loading
            self.model = AutoModel.from_pretrained(
                self.model_id,
                # Depending on the system's exact RAM, these can be adjusted.
                # AirLLM handles most of the memory mapping automatically.
            )
            
            self.is_loaded = True
            logger.info("[Deep Thought] AirLLM Successfully Bound to System Architecture.")
            
        except Exception as e:
            logger.error(f"[Deep Thought] Failed to bind AirLLM: {str(e)}")
            raise e
            
    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
        """
        Generate a response using the locally cached massive model.
        """
        if not self.is_loaded:
            self.load()
            
        import torch
        from transformers import AutoTokenizer
        
        try:
            if not self.tokenizer:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                
            logger.info(f"[Deep Thought] Processing Deep Request ({len(prompt)} chars)...")
            start_time = time.time()
            
            # Format as conversation instruction (this depends slightly on the specific model)
            input_text = f"Instruction: {prompt}\n\nResponse:"
            input_tokens = self.tokenizer(
                input_text,
                return_tensors="pt",
                return_attention_mask=False,
                truncation=True,
                max_length=4096 
            )
            
            # Generation requires the explicit AirLLM generation method
            generation_output = self.model.generate(
                input_tokens['input_ids'].cuda(),
                max_new_tokens=max_new_tokens,
                use_cache=True, 
                return_dict_in_generate=True
            )
            
            # Decode output
            decoded = self.tokenizer.decode(generation_output.sequences[0], skip_special_tokens=True)
            
            # Strip the prompt from the final response if necessary
            response = decoded.replace(input_text, "").strip()
            
            latency = time.time() - start_time
            logger.info(f"[Deep Thought] Inference Complete. Latency: {latency:.2f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"[Deep Thought] Inference Kernel Panic: {str(e)}")
            return f"Error during Deep Thought Generation: {str(e)}"

# Singleton instance for the backend
deep_thought_engine = AirLLMEngine()
