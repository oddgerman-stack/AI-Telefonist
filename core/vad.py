import os
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from core.config import config

class SileroVAD:
    """
    Silero VAD v5 speech start/end detection engine.
    Processes audio chunks (512 samples @ 16kHz = 32ms) and detects voice activity.
    Supports ONNX Runtime (CPU or DirectML/GPU) with energy-based fallback.
    """

    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5):
        self.threshold = threshold
        self.sample_rate = config.get("pipeline.sample_rate", 16000)
        configured_path = model_path or config.get("pipeline.vad.model_path", "models/vad/silero_vad.onnx")
        self.model_path = config.resolve_path(configured_path)
        
        self.session = None
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._sr_tensor = np.array([self.sample_rate], dtype=np.int64)
        
        # State tracking for speech turn-taking
        self.is_speaking = False
        self.silence_chunks = 0
        self.speech_chunks = 0
        
        # 700ms silence threshold before concluding user finished turn
        self.silence_limit_chunks = int(config.get("pipeline.vad.silence_duration_ms", 700) / 32)
        self.min_speech_chunks = int(config.get("pipeline.vad.min_speech_duration_ms", 250) / 32)
        
        self._load_model()

    def _load_model(self) -> None:
        """Loads Silero VAD v5 ONNX session."""
        if not self.model_path.exists():
            print(f"[VAD] Notice: Silero VAD model not found at {self.model_path}. Using energy fallback.")
            return

        try:
            import onnxruntime as ort
            # Try DirectML or CUDA providers if available, fallback to CPU
            providers = ["CPUExecutionProvider"]
            available = ort.get_available_providers()
            if "DmlExecutionProvider" in available:
                providers.insert(0, "DmlExecutionProvider")
            elif "CUDAExecutionProvider" in available:
                providers.insert(0, "CUDAExecutionProvider")

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            self.session = ort.InferenceSession(str(self.model_path), sess_options=opts, providers=providers)
            self.reset_state()
            print(f"[VAD] Silero VAD v5 loaded successfully with providers: {self.session.get_providers()}")
        except Exception as e:
            print(f"[VAD] Failed to initialize ONNX runtime session: {e}. Falling back to energy detector.")
            self.session = None

    def reset_state(self) -> None:
        """Reset internal recurrent state of Silero VAD."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self.is_speaking = False
        self.silence_chunks = 0
        self.speech_chunks = 0

    def process_chunk(self, audio_chunk: np.ndarray) -> Tuple[float, bool, bool]:
        """
        Process a 32ms audio chunk (512 samples at 16kHz).
        Returns:
            (probability: float, speech_started: bool, speech_ended: bool)
        """
        # Ensure float32 in [-1.0, 1.0]
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0

        if len(audio_chunk) < 512:
            audio_chunk = np.pad(audio_chunk, (0, 512 - len(audio_chunk)))
        elif len(audio_chunk) > 512:
            audio_chunk = audio_chunk[:512]

        prob = 0.0
        if self.session is not None:
            try:
                # Silero v5 input: input (1, 512), state (2, 1, 128), sr (1,)
                ort_inputs = {
                    "input": np.expand_dims(audio_chunk, axis=0),
                    "state": self._state,
                    "sr": self._sr_tensor
                }
                out, new_state = self.session.run(None, ort_inputs)
                self._state = new_state
                prob = float(out[0][0])
            except Exception as e:
                prob = self._energy_detection(audio_chunk)
        else:
            prob = self._energy_detection(audio_chunk)

        started = False
        ended = False

        if prob >= self.threshold:
            self.speech_chunks += 1
            self.silence_chunks = 0
            if not self.is_speaking and self.speech_chunks >= self.min_speech_chunks:
                self.is_speaking = True
                started = True
        else:
            if self.is_speaking:
                self.silence_chunks += 1
                if self.silence_chunks >= self.silence_limit_chunks:
                    self.is_speaking = False
                    ended = True
                    self.speech_chunks = 0
                    self.silence_chunks = 0
            else:
                self.speech_chunks = 0

        return prob, started, ended

    def _energy_detection(self, chunk: np.ndarray) -> float:
        """Energy heuristic fallback when ONNX model is missing."""
        rms = np.sqrt(np.mean(chunk ** 2) + 1e-9)
        # Scaled heuristic: noise floor ~0.005, speech ~0.03+
        normalized = np.clip((rms - 0.008) / 0.04, 0.0, 1.0)
        return float(normalized)
