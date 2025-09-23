# path: backend/services/llm_wrapper.py
from __future__ import annotations

import json
import os
import threading
from typing import Dict, List, Optional

def _load_config() -> Dict:
    try:
        import yaml
        with open(os.path.join("config", "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"llm": {"path": "models/llm/llama-3.2-3b-instruct-q4_ks.gguf", "threads": 8, "ctx": 2048, "n_gpu_layers": 0, "temperature": 0.2}}

class LLMWrapper:
    """
    llama.cpp-backed local model for STRICT JSON completions.
    Used only to fill ambiguous VisitJSON slots. Offline-only.
    """
    _instance: Optional["LLMWrapper"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "LLMWrapper":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.cfg = _load_config()
        self._model = None
        try:
            from llama_cpp import Llama
            p = self.cfg["llm"]["path"]
            self._model = Llama(
                model_path=p,
                n_ctx=self.cfg["llm"].get("ctx", 2048),
                n_threads=self.cfg["llm"].get("threads", 8),
                n_gpu_layers=self.cfg["llm"].get("n_gpu_layers", 0),
                verbose=False,
            )
        except Exception:
            self._model = None  # stub mode

    def complete_json(self, prompt: str, keys: List[str]) -> Dict:
        """
        Returns a dict with only the requested keys.
        If model not available, returns {}.
        """
        if self._model is None:
            return {}
        # Instruct for JSON only
        sys = "Respond strictly in compact JSON with only the requested keys. No prose."
        user = f"Required keys: {keys}. {prompt}"
        try:
            out = self._model.create_chat_completion(
                messages=[
                    {"role": "system", "content": sys},
                    {"role": "user", "content": user},
                ],
                temperature=self.cfg["llm"].get("temperature", 0.2),
                max_tokens=160,
                response_format={"type": "json_object"},
            )
            txt = out["choices"][0]["message"]["content"]
            js = json.loads(txt)
            # keep only requested keys
            return {k: js.get(k) for k in keys}
        except Exception:
            return {}
