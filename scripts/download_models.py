import os
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"

DOWNLOADS = {
    "vad": {
        "url": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
        "dest": MODELS_DIR / "vad" / "silero_vad.onnx"
    },
    "piper_nl": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_BE/nathalie/x_low/nl_BE-nathalie-x_low.onnx",
        "dest": MODELS_DIR / "piper" / "nl_NL-mls_7432-low.onnx"
    },
    "piper_nl_json": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_BE/nathalie/x_low/nl_BE-nathalie-x_low.onnx.json",
        "dest": MODELS_DIR / "piper" / "nl_NL-mls_7432-low.onnx.json"
    },
    "piper_en": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low/en_US-amy-low.onnx",
        "dest": MODELS_DIR / "piper" / "en_US-amy-low.onnx"
    },
    "piper_en_json": {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low/en_US-amy-low.onnx.json",
        "dest": MODELS_DIR / "piper" / "en_US-amy-low.onnx.json"
    }
}

def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[Skip] Already exists: {dest.name}")
        return

    print(f"[Downloading] {dest.name} from {url}...")
    try:
        def progress(count, block_size, total_size):
            if total_size > 0:
                pct = int(count * block_size * 100 / total_size)
                print(f"\r  Progress: {pct}%", end="")

        urllib.request.urlretrieve(url, str(dest), reporthook=progress)
        print(f"\n[Done] Saved to {dest}")
    except Exception as e:
        print(f"\n[Warning] Could not download {dest.name}: {e}")

def main():
    print("==================================================")
    print(" AI-Telefonist • Offline Model Weights Fetcher")
    print("==================================================")
    for key, item in DOWNLOADS.items():
        download_file(item["url"], item["dest"])

    print("\nNote for Qwen 2.5 GGUF & llama-server.exe:")
    print("1. Download Qwen2.5 GGUF (e.g. qwen2.5-7b-instruct-q4_k_m.gguf) into models/llm/")
    print("2. Place llama-server.exe into bin/llama/")
    print("All models operate 100% offline with zero cloud fees.")

if __name__ == "__main__":
    main()
