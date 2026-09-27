import logging
import time
import requests
from typing import Dict, Any, Optional
from app.rag.config import settings

logger = logging.getLogger(__name__)

class LocalLLMService:
    """
    Abstraction Layer for local offline LLM interactions via Ollama.
    Enables future agent extensions to consume LLM capabilities deterministically and with structured control.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 768,
        timeout: int = settings.OLLAMA_TIMEOUT,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.LOCAL_LLM_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_format: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes generation request against Ollama and measures latency.
        Returns:
            Dict containing 'response', 'latency_ms', and 'error' if any.
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        to = timeout if timeout is not None else self.timeout

        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": tokens,
                "num_ctx": 2048
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        if json_format:
            payload["format"] = "json"

        t0 = time.perf_counter()
        try:
            response = requests.post(url, json=payload, timeout=to)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            if response.status_code == 200:
                result = response.json()
                return {
                    "response": result.get("response", "").strip(),
                    "latency_ms": latency_ms,
                    "error": None
                }
            else:
                error_msg = f"Ollama HTTP error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "response": "",
                    "latency_ms": latency_ms,
                    "error": error_msg
                }
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            error_msg = f"Failed to connect to local Ollama: {e}"
            logger.error(error_msg)
            return {
                "response": "",
                "latency_ms": latency_ms,
                "error": error_msg
            }
