import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path
from typing import Generator, List, Dict, Any, Optional
from core.config import config

class LocalLLM:
    """
    Connects to local Qwen 2.5 LLM via llama.cpp server (or Ollama).
    Provides low-latency token streaming for sentence chunking and real-time TTS.
    """

    def __init__(self):
        self.api_url = config.get("pipeline.llm.api_url", "http://127.0.0.1:8080/v1/chat/completions")
        self.model_path = config.resolve_path(config.get("pipeline.llm.model_path", "models/llm/qwen2.5-7b-instruct-q4_k_m.gguf"))
        self.server_bin = config.resolve_path(config.get("pipeline.llm.server_bin", "bin/llama/llama-server.exe"))
        self.n_gpu_layers = config.get("pipeline.llm.n_gpu_layers", -1)
        self.ctx_size = config.get("pipeline.llm.ctx_size", 4096)
        self.temperature = config.get("pipeline.llm.temperature", 0.4)
        
        self.server_process: Optional[subprocess.Popen] = None

    def start_server_if_needed(self) -> bool:
        """Starts the embedded llama-server.exe if present and not already running."""
        # Test if server is already reachable
        try:
            health_url = self.api_url.replace("/chat/completions", "/models").replace("/v1/models", "/health")
            res = requests.get(health_url, timeout=1.0)
            if res.status_code == 200:
                print("[LLM] Local llama-server is already active and responsive.")
                return True
        except Exception:
            pass

        if not self.server_bin.exists():
            print(f"[LLM] llama-server executable not found at {self.server_bin}. Waiting for external server or simulation.")
            return False

        if not self.model_path.exists():
            print(f"[LLM] Qwen2.5 GGUF weights not found at {self.model_path}.")
            return False

        cmd = [
            str(self.server_bin),
            "-m", str(self.model_path),
            "-c", str(self.ctx_size),
            "-ngl", str(self.n_gpu_layers),
            "--host", "127.0.0.1",
            "--port", "8080"
        ]

        try:
            print(f"[LLM] Spawning local llama-server: {' '.join(cmd)}")
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            self.server_process = subprocess.Popen(cmd, creationflags=creationflags)
            
            # Wait up to 10 seconds for server to bind
            for _ in range(20):
                time.sleep(0.5)
                try:
                    res = requests.get("http://127.0.0.1:8080/health", timeout=0.5)
                    if res.status_code == 200:
                        print("[LLM] Local llama-server is ready.")
                        return True
                except Exception:
                    pass
            print("[LLM] Server started but health check timed out. Proceeding.")
            return True
        except Exception as e:
            print(f"[LLM] Could not launch llama-server: {e}")
            return False

    def stop_server(self) -> None:
        """Terminates spawned server process cleanly."""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=3)
            except Exception:
                self.server_process.kill()
            self.server_process = None
            print("[LLM] llama-server stopped.")

    def stream_chat(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """
        Stream tokens from Qwen 2.5 via SSE.
        Yields individual text tokens as they are produced by the GPU/CPU.
        """
        payload = {
            "model": "qwen2.5",
            "messages": messages,
            "temperature": self.temperature,
            "stream": True,
            "max_tokens": 512
        }

        try:
            with requests.post(self.api_url, json=payload, stream=True, timeout=15.0) as response:
                if response.status_code != 200:
                    yield from self._fallback_response(messages)
                    return

                for line in response.iter_lines():
                    if not line:
                        continue
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        raw_data = line_text[6:].strip()
                        if raw_data == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(raw_data)
                            delta = chunk_json.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception as e:
            print(f"[LLM] Error connecting to local server ({self.api_url}): {e}")
            yield from self._fallback_response(messages)

    def _fallback_response(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """Heuristic fallback for offline/testing when LLM server is initializing."""
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "").lower()
                break

        # Check language
        is_english = any(w in last_user_msg for w in ["hello", "appointment", "meeting", "call", "schedule", "english"])
        if is_english:
            reply = "Thank you for calling. I would be happy to schedule that appointment for you. May I please have your full name and phone number?"
        else:
            reply = "Hartelijk dank voor uw bericht. Ik plan deze afspraak graag voor u in. Mag ik uw volledige naam en telefoonnummer noteren?"

        # Yield simulated token chunks with micro-delays
        words = reply.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            time.sleep(0.04)
