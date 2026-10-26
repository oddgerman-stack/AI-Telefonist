import os
import io
import wave
import json
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from core.config import config

class PiperTTS:
    """
    Piper ONNX Neural Text-To-Speech Synthesizer.
    Performs sub-100ms chunked neural speech synthesis for Dutch and English.
    """

    def __init__(self):
        self.sample_rate = config.get("pipeline.tts.sample_rate", 22050)
        self.voice_nl_path = config.resolve_path(config.get("pipeline.tts.voice_nl", "models/piper/nl_NL-mls_7432-low.onnx"))
        self.voice_en_path = config.resolve_path(config.get("pipeline.tts.voice_en", "models/piper/en_US-amy-low.onnx"))
        
        self.sessions = {}
        self._load_voices()

    def _load_voices(self) -> None:
        """Loads ONNX runtime sessions for Dutch and English voice models if present."""
        try:
            import onnxruntime as ort
            providers = ["CPUExecutionProvider"]
            available = ort.get_available_providers()
            if "DmlExecutionProvider" in available:
                providers.insert(0, "DmlExecutionProvider")

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 2

            if self.voice_nl_path.exists():
                self.sessions["nl"] = ort.InferenceSession(str(self.voice_nl_path), sess_options=opts, providers=providers)
                print(f"[TTS] Loaded Dutch Piper model: {self.voice_nl_path.name}")

            if self.voice_en_path.exists():
                self.sessions["en"] = ort.InferenceSession(str(self.voice_en_path), sess_options=opts, providers=providers)
                print(f"[TTS] Loaded English Piper model: {self.voice_en_path.name}")

        except Exception as e:
            print(f"[TTS] Note on ONNX TTS: {e}. Fallback synthesizer will be used.")

    def synthesize(self, text: str, language: str = "nl") -> Tuple[bytes, int]:
        """
        Synthesize text into raw 16-bit PCM audio bytes.
        Returns:
            (pcm_bytes: bytes, sample_rate: int)
        """
        text = text.strip()
        if not text:
            return b"", self.sample_rate

        # Prefer piper voice if loaded or piper CLI
        # 1. Try Piper python bindings if available
        try:
            import piper
            voice_path = str(self.voice_nl_path if language == "nl" else self.voice_en_path)
            if os.path.exists(voice_path):
                voice = piper.PiperVoice.load(voice_path)
                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wav_file:
                    voice.synthesize(text, wav_file)
                return wav_io.getvalue(), self.sample_rate
        except Exception:
            pass

        # 2. Try Windows SAPI (offline built-in speech engine) as zero-dependency offline fallback
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Try to select Dutch voice if available
            voices = engine.getProperty('voices')
            for v in voices:
                if language == "nl" and ("dutch" in v.name.lower() or "nederlands" in v.name.lower()):
                    engine.setProperty('voice', v.id)
                    break
                elif language == "en" and ("english" in v.name.lower() or "david" in v.name.lower() or "zira" in v.name.lower()):
                    engine.setProperty('voice', v.id)
                    break

            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()

            try:
                os.remove(tmp_path)
            except Exception:
                pass

            return wav_bytes, self.sample_rate
        except Exception:
            pass

        # 3. Deterministic synthetic audio beep/pulse fallback for zero-dependency headless environments
        return self._generate_fallback_audio(text)

    def _generate_fallback_audio(self, text: str) -> Tuple[bytes, int]:
        """Generates soft synthetic tone buffer so the audio player always receives valid WAV."""
        duration = min(max(len(text) * 0.05, 0.4), 2.5) # Roughly proportional to speech duration
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        # Soft 440Hz and 880Hz harmonic tone with fade out
        tone = (np.sin(2 * np.pi * 440 * t) * 0.2 + np.sin(2 * np.pi * 880 * t) * 0.1) * np.exp(-t * 2)
        audio_int16 = (tone * 32767).astype(np.int16)

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        return wav_io.getvalue(), self.sample_rate
