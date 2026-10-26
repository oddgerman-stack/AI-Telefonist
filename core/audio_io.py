import queue
import numpy as np
from typing import Optional, Callable
from core.config import config

class LocalAudioIO:
    """
    Manages local hardware microphone capture and speaker playback on Windows.
    Provides non-blocking stream callback buffers for real-time VAD & TTS output.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.input_queue: queue.Queue = queue.Queue()
        self.output_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self._in_stream = None
        self._out_stream = None

    def start_recording(self, on_chunk: Optional[Callable[[np.ndarray], None]] = None) -> bool:
        """Start recording from the default Windows microphone device."""
        try:
            import sounddevice as sd

            def audio_callback(indata, frames, time_info, status):
                chunk = indata[:, 0].copy() # Mono
                self.input_queue.put(chunk)
                if on_chunk:
                    on_chunk(chunk)

            self._in_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=512, # 32ms chunk for Silero VAD
                callback=audio_callback
            )
            self._in_stream.start()
            self.is_running = True
            print("[AudioIO] Microphone stream started.")
            return True
        except Exception as e:
            print(f"[AudioIO] Could not start microphone stream: {e}")
            return False

    def stop_recording(self) -> None:
        """Stop microphone capture."""
        if self._in_stream:
            try:
                self._in_stream.stop()
                self._in_stream.close()
            except Exception:
                pass
            self._in_stream = None
        self.is_running = False
        print("[AudioIO] Microphone stream stopped.")

    def play_audio(self, audio_data: np.ndarray, sample_rate: int = 22050) -> None:
        """Play synthesized audio chunk through default Windows speaker."""
        try:
            import sounddevice as sd
            sd.play(audio_data, samplerate=sample_rate)
        except Exception as e:
            print(f"[AudioIO] Playback error: {e}")
