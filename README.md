# AI-Telefonist 📞🇳🇱🇬🇧
> **100% Offline, Zero-Cloud-Fee Autonomous Virtual Front-Desk Receptionist for Windows**

AI-Telefonist is an enterprise-grade virtual telephone receptionist that runs completely locally on your hardware. It handles incoming telephone inquiries, schedules appointments, performs intake questionnaires, produces standard `.ics` calendar invites, and dispatches real-time notifications via SMTP email and Webhooks (Discord, Slack, n8n, Zapier).

---

## 🏗️ Architecture & Conversational Pipeline

The system is powered by a low-latency **Streaming Cascade** speech-to-speech architecture:

```
Microphone Audio (Browser / Windows WASAPI)
      │
[Silero VAD v5] ──── (Speech Start / End & Turn-Taking Detection)
      │
[Faster-Whisper] ─── (Streaming ASR with Automatic Dutch / English Detection)
      │
[Local LLM (Qwen 2.5)] ── (Streaming Token Generation via llama.cpp / Ollama)
      │
[Sentence / Clause Chunker] ── (Buffers tokens into natural clauses at punctuation)
      │
[Piper ONNX TTS] ─── (Sub-100ms Chunked Neural Audio Synthesis in NL & EN)
      │
Speaker Audio / WebSocket Audio Stream
```

---

## 🌟 Key Features

1. **Zero External Dependencies & Zero Cloud Fees**:
   - Runs 100% offline on local GPU (AMD Radeon RX / DirectML, NVIDIA CUDA, or optimized CPU).
   - No monthly API costs, zero data leakage, and total privacy for business telephony.

2. **Strict Dual-Language Operation (Dutch & English Only)**:
   - **Standaard in het Nederlands**: Automatically greets and converses in Dutch.
   - **Auto-Language Switching**: Seamlessly detects when the caller speaks English and adapts instantly.

3. **Structured Intake Questionnaires**:
   - Automatically identifies and extracts caller slots in real-time:
     - Caller Name
     - Company / Organization
     - Callback Phone & Email
     - Reason / Subject of Call
     - Requested Date & Time

4. **Calendar & Appointments Database**:
   - Persists bookings into thread-safe `appointments.json`.
   - **Natural Date-Time Parsing**: Parses natural expressions like `"morgen om 14 uur"`, `"volgende week woensdag om 10:30"`, `"next Monday at 2 PM"` into standard ISO-8601 datetimes.
   - **RFC 5545 `.ics` iCalendar Generator**: 1-click download of calendar invites compatible with Outlook, Google Calendar, and Apple Calendar.
   - Time-slot conflict detection.

5. **Real-Time Multi-Channel Dispatcher**:
   - **SMTP Email**: Delivers formatted HTML summary emails with the `.ics` calendar invite attached.
   - **Webhooks**: Instantly sends rich Discord embeds, Slack Block Kit cards, or generic JSON payloads to n8n / Zapier / Make.
   - **Calendar Sync**: Extensible stubs for Google Calendar API and Cal.com.

6. **Modern Glassmorphic Web Interface**:
   - Live Call Console with real-time audio waveform visualizer.
   - Duplex WebSocket audio streaming (browser mic ↔ server speech cascade).
   - Live intake checklist and dialogue feed with NL/EN badges.
   - Appointments viewer with filter pills, search bar, and one-click `.ics` downloads.
   - Full settings panel for business profile, voices, SMTP, and Webhooks.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Windows 10 / 11 (64-bit)
- Python 3.10, 3.11, or 3.12
- (Optional for GPU): AMD Radeon GPU (DirectML/ROCm) or NVIDIA GPU (CUDA)

### 2. Installation
```powershell
# Clone or open the repository
git clone https://github.com/oddgerman-stack/AI-Telefonist.git
cd AI-Telefonist

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Fetch Offline Model Weights
Run the automated downloader to fetch Silero VAD v5 and Piper ONNX Dutch/English neural voices:
```powershell
python scripts/download_models.py
```

Place your preferred **Qwen 2.5 GGUF** model (e.g. `qwen2.5-7b-instruct-q4_k_m.gguf`) in `models/llm/` and `llama-server.exe` in `bin/llama/`.

### 4. Start the Application
Run via batch script or PowerShell:
```powershell
.\run.bat
# or
python -m web.app
```
Open your browser at **`http://127.0.0.1:8000`**.

---

## 📦 Windows Compilation & Packaging

### 1. PyInstaller Executable (`build_exe.py`)
Generates a lightweight (~45 MB) standalone executable that embeds only Python code, dependencies, and web templates:
```powershell
python scripts/build_exe.py
```
*Note: Large model weights (2GB+) are intentionally kept outside the binary to avoid Windows PE / Inno Setup disk spanning limits (> 4 GB).*

### 2. Inno Setup Single-File Installer (`AI-Telefonist-Installer.exe`)
Compiles a complete Windows installer with LZMA2/max compression, packaging the executable, `models/`, and `bin/llama/`:
```powershell
python scripts/build_installer.py
```
**Installer Highlights**:
- Automatically terminates running instances (`ai-telefonist.exe`, `llama-server.exe`) before install/uninstall.
- Registers standard Windows Registry keys.
- **Clean Uninstallation**: Executes `DelTree` on post-uninstall to cleanly wipe runtime directories, appointments, and logs.

---

## ⚙️ Configuration (`config.json`)

```json
{
  "business": {
    "name": "Acme Bedrijf B.V.",
    "phone": "+31 (0)20 123 4567",
    "receptionist_name": "Sarah",
    "opening_hours": "Maandag t/m Vrijdag van 08:30 tot 17:30 uur",
    "default_language": "nl"
  },
  "pipeline": {
    "sample_rate": 16000,
    "vad": { "threshold": 0.5, "silence_duration_ms": 700 },
    "asr": { "model_size": "large-v3-turbo", "default_language": "nl" },
    "llm": { "api_url": "http://127.0.0.1:8080/v1/chat/completions" }
  },
  "notifications": {
    "smtp": {
      "enabled": false,
      "host": "smtp.example.com",
      "port": 587,
      "recipient_email": "frontdesk@example.com"
    },
    "webhooks": {
      "enabled": false,
      "discord_url": "",
      "slack_url": ""
    }
  }
}
```

---

## 📄 License
MIT License. Built for autonomous, zero-cost, enterprise-grade telephone reception.
