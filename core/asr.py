import os
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from core.config import config

class WhisperASR:
    """
    Faster-Whisper Streaming ASR with Dual-Language (NL / EN) detection.
    Optimized for low-latency Dutch & English front-desk telephone transcription.
    """

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or config.get("pipeline.asr.model_size", "large-v3-turbo")
        self.device = config.get("pipeline.asr.device", "auto")
        self.compute_type = config.get("pipeline.asr.compute_type", "float16")
        self.default_lang = config.get("pipeline.asr.default_language", "nl")
        self.supported_langs = config.get("pipeline.asr.supported_languages", ["nl", "en"])
        
        configured_path = config.get("pipeline.asr.model_path", f"models/whisper/{self.model_size}")
        self.model_path = config.resolve_path(configured_path)
        
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Loads Faster-Whisper model if installed and available."""
        try:
            from faster_whisper import WhisperModel

            # Resolve actual model directory or download alias
            model_source = str(self.model_path) if self.model_path.exists() else self.model_size
            
            # Auto-detect device
            device = self.device
            compute_type = self.compute_type
            if device == "auto":
                try:
                    import ctranslate2
                    if ctranslate2.get_cuda_device_count() > 0:
                        device = "cuda"
                    else:
                        device = "cpu"
                        compute_type = "int8"
                except Exception:
                    device = "cpu"
                    compute_type = "int8"

            print(f"[ASR] Initializing Faster-Whisper ({model_source}) on {device} ({compute_type})...")
            self.model = WhisperModel(
                model_source,
                device=device,
                compute_type=compute_type,
                cpu_threads=4,
                num_workers=1
            )
            print("[ASR] Faster-Whisper loaded successfully.")
        except ImportError:
            print("[ASR] faster_whisper package not installed. Running in simulation mode.")
            self.model = None
        except Exception as e:
            print(f"[ASR] Error loading Faster-Whisper: {e}. Running in simulation mode.")
            self.model = None

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> Tuple[str, str, float]:
        """
        Transcribe audio buffer and detect spoken language.
        Returns:
            (transcript: str, language: str ('nl' or 'en'), confidence: float)
        """
        if self.model is None:
            # Fallback for headless environments or before model download
            return "Goedendag, ik wil graag een afspraak inplannen voor morgen om 14 uur.", "nl", 0.99

        # Ensure float32 normalized between -1.0 and 1.0
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        try:
            # Transcribe with automatic language detection constrained to NL and EN
            segments, info = self.model.transcribe(
                audio,
                beam_size=3,
                word_timestamps=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                language=None # Allow model to detect
            )

            detected_lang = info.language
            # Restrict strictly to English or Dutch
            if detected_lang not in self.supported_langs:
                detected_lang = self.default_lang

            text_chunks = [segment.text.strip() for segment in segments]
            full_text = " ".join(text_chunks).strip()
            confidence = float(info.language_probability)

            return full_text, detected_lang, confidence

        except Exception as e:
            print(f"[ASR] Transcription error: {e}")
            return "", self.default_lang, 0.0
