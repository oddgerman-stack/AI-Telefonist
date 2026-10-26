import asyncio
import numpy as np
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from core.config import config
from core.vad import SileroVAD
from core.asr import WhisperASR
from core.llm import LocalLLM
from core.chunker import StreamChunker
from core.tts import PiperTTS

class VoicePipeline:
    """
    Streaming Cascade Speech-to-Speech Engine:
    Microphone -> Silero VAD v5 -> Faster-Whisper ASR -> Local LLM -> Stream Chunker -> Piper ONNX TTS -> Speaker
    """

    def __init__(self):
        self.vad = SileroVAD()
        self.asr = WhisperASR()
        self.llm = LocalLLM()
        self.chunker = StreamChunker()
        self.tts = PiperTTS()

        self.sample_rate = config.get("pipeline.sample_rate", 16000)
        self.current_language = config.get("business.default_language", "nl")
        self.conversation_history: List[Dict[str, str]] = []

    def reset_conversation(self, system_prompt: str) -> None:
        """Reset history and set front-desk persona system prompt."""
        self.conversation_history = [
            {"role": "system", "content": system_prompt}
        ]
        self.current_language = config.get("business.default_language", "nl")
        self.vad.reset_state()

    def set_system_prompt(self, system_prompt: str) -> None:
        """Update or insert system prompt at the beginning of history."""
        if self.conversation_history and self.conversation_history[0].get("role") == "system":
            self.conversation_history[0]["content"] = system_prompt
        else:
            self.conversation_history.insert(0, {"role": "system", "content": system_prompt})

    def process_speech_turn(self, audio_buffer: np.ndarray) -> Dict[str, Any]:
        """
        Processes a complete user utterance from audio buffer:
        1. Transcribes via Whisper & detects language (NL/EN)
        2. Queries Qwen 2.5 LLM with conversation history
        3. Returns user transcript, detected language, and an iterator of audio chunks
        """
        # 1. ASR
        user_transcript, detected_lang, confidence = self.asr.transcribe(audio_buffer, self.sample_rate)
        if not user_transcript.strip():
            return {
                "transcript": "",
                "language": self.current_language,
                "confidence": 0.0,
                "audio_chunks": []
            }

        self.current_language = detected_lang
        self.conversation_history.append({"role": "user", "content": user_transcript})

        # 2. LLM Streaming
        token_stream = self.llm.stream_chat(self.conversation_history)

        # 3. Chunker & TTS
        text_chunks = []
        full_reply = ""

        def generate_audio_stream():
            nonlocal full_reply
            for chunk_text in self.chunker.chunk_tokens(token_stream):
                full_reply += chunk_text + " "
                wav_bytes, sr = self.tts.synthesize(chunk_text, self.current_language)
                yield {
                    "text": chunk_text,
                    "wav_bytes": wav_bytes,
                    "sample_rate": sr,
                    "language": self.current_language
                }
            self.conversation_history.append({"role": "assistant", "content": full_reply.strip()})

        return {
            "transcript": user_transcript,
            "language": self.current_language,
            "confidence": confidence,
            "audio_stream": generate_audio_stream()
        }
