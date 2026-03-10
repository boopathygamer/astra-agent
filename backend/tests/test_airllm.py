import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock optimum globally to prevent AirLLM from crashing on missing Windows binaries during tests
sys.modules["optimum"] = MagicMock()
sys.modules["optimum.bettertransformer"] = MagicMock()

# Add parent dir to path so we can import internal modules easily
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.airllm_engine import AirLLMEngine, deep_thought_engine

@patch("airllm.AutoModel")
def test_airllm_initialization(mock_auto_model):
    """
    Test that the AirLLMEngine wrapper initializes the AutoModel correctly.
    Since AirLLM downloads massive gigabytes of data, we mock the heavy lifting
    to ensure the architecture integration is solid.
    """
    # Create a fresh engine instance to avoid side-effects
    engine = AirLLMEngine(model_id="test/platypus-mock")
    
    assert not engine.is_loaded
    
    # Trigger lazy load
    engine.load()
    
    assert engine.is_loaded
    mock_auto_model.from_pretrained.assert_called_once_with("test/platypus-mock")


@patch("airllm.AutoModel")
@patch("transformers.AutoTokenizer")
def test_airllm_generation(mock_auto_tokenizer, mock_auto_model):
    """
    Test that the generation pipe processes tokens through the swapped layers and
    returns a decoded string to the requester.
    """
    # Setup mocks
    mock_model_instance = MagicMock()
    mock_auto_model.from_pretrained.return_value = mock_model_instance
    
    mock_gen_output = MagicMock()
    mock_gen_output.sequences = [["mock_token_id"]]
    mock_model_instance.generate.return_value = mock_gen_output
    
    mock_tokenizer_instance = MagicMock()
    mock_tokenizer_instance.return_value = {"input_ids": MagicMock()}
    mock_tokenizer_instance.decode.return_value = "Instruction: Explain AI\n\nResponse: Complex Abstract Logic"
    mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer_instance
    
    # Test execution
    engine = AirLLMEngine("test/mock-70b")
    response = engine.generate("Explain AI", max_new_tokens=10)
    
    # Validate calls
    assert engine.is_loaded
    mock_tokenizer_instance.assert_called()
    mock_model_instance.generate.assert_called_once()
    assert response == "Complex Abstract Logic"

