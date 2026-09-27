import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Setup path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.llm import LocalLLMService
from app.rag.config import settings

# -----------------------------------------------------------------------------
# 1. Mocked Unit Tests
# -----------------------------------------------------------------------------

@patch("requests.post")
def test_local_llm_service_successful_mocked(mock_post):
    """Test successful generation using mocked requests.post."""
    # Set up mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Mocked Ollama Answer"}
    mock_post.return_value = mock_response

    # Initialize service
    llm = LocalLLMService(temperature=0.5, max_tokens=100)
    res = llm.generate("Hello world")

    # Assertions
    assert res["error"] is None
    assert res["response"] == "Mocked Ollama Answer"
    assert res["latency_ms"] > 0
    mock_post.assert_called_once()
    
    # Check payload parameters
    args, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["model"] == settings.LOCAL_LLM_MODEL
    assert payload["options"]["temperature"] == 0.5
    assert payload["options"]["num_predict"] == 100

@patch("requests.post")
def test_local_llm_service_failure_mocked(mock_post):
    """Test connection error handling using mocked requests.post."""
    mock_post.side_effect = Exception("Connection Refused")

    llm = LocalLLMService()
    res = llm.generate("Hello")

    assert res["error"] is not None
    assert "Failed to connect to local Ollama" in res["error"]
    assert res["response"] == ""

# -----------------------------------------------------------------------------
# 2. Real Integration Test
# -----------------------------------------------------------------------------

def test_local_llm_service_real_integration():
    """Real integration test verifying Ollama is reachable, model is present, and generation succeeds."""
    import requests
    
    # Initialize service
    llm = LocalLLMService()
    
    # Check 1: Reachability
    try:
        resp = requests.get(f"{llm.base_url.rstrip('/')}/api/tags", timeout=5)
        assert resp.status_code == 200, f"Ollama not reachable: status {resp.status_code}"
        models = [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        pytest.fail(f"Ollama local service is not reachable at {llm.base_url}. Error: {e}")

    # Check 2: Model availability
    assert any(llm.model in m for m in models), f"Configured model '{llm.model}' not found in available Ollama models: {models}"

    # Check 3: Generation successful
    res = llm.generate("Reply with 'yes' or 'no'. Are you online?")
    assert res["error"] is None, f"Generation failed: {res['error']}"
    assert len(res["response"].strip()) > 0, "Response from Ollama was empty"
