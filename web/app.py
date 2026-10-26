import os
import sys
import json
import base64
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import numpy as np

from core.config import config, get_bundle_dir
from core.pipeline import VoicePipeline
from receptionist.prompts import get_receptionist_system_prompt
from receptionist.intake import IntakeSession
from storage.database import db
from storage.ical_generator import ICalGenerator
from notifications.dispatcher import NotificationDispatcher

# Application Setup
app = FastAPI(title="AI-Telefonist", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bundle_dir = get_bundle_dir()
static_dir = bundle_dir / "web" / "static"
templates_dir = bundle_dir / "web" / "templates"

# Fallback if running outside root
if not static_dir.exists():
    static_dir = Path(__file__).parent / "static"
if not templates_dir.exists():
    templates_dir = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Shared voice pipeline instance
pipeline = VoicePipeline()

# --- WEB DASHBOARD ROUTE ---

@app.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    """Renders main AI-Telefonist dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "config": config.data,
            "version": "1.0.0"
        }
    )

# --- APPOINTMENTS REST API ---

@app.get("/api/appointments")
async def list_appointments(status: Optional[str] = None, search: Optional[str] = None):
    """List appointments with optional filtering."""
    return db.list_all(status=status, search=search)

@app.post("/api/appointments")
async def create_appointment(data: Dict[str, Any]):
    """Manually book an appointment and trigger dispatch."""
    # Check for slot conflicts
    start_time = data.get("start_time")
    if start_time:
        conflict = db.check_conflict(start_time, data.get("duration_minutes", 30))
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Tijdstip overlapt met bestaande afspraak voor {conflict.get('caller_name')}."
            )

    appointment = db.add(data)
    # Trigger notifications
    NotificationDispatcher.dispatch_appointment(appointment)
    return {"status": "success", "appointment": appointment}

@app.get("/api/appointments/{appointment_id}/ics")
async def download_ics(appointment_id: str):
    """One-click standard .ics iCalendar download endpoint."""
    appointment = db.get_by_id(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Afspraak niet gevonden.")

    ics_content = ICalGenerator.generate_bytes(appointment)
    filename = f"afspraak_{appointment.get('caller_name', 'klant').replace(' ', '_')}.ics"
    
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/appointments/{appointment_id}/dispatch")
async def trigger_dispatch(appointment_id: str):
    """Manually trigger multi-channel email/webhook dispatch."""
    appointment = db.get_by_id(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Afspraak niet gevonden.")

    NotificationDispatcher.dispatch_appointment(appointment)
    return {"status": "dispatched", "appointment_id": appointment_id}

@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str):
    """Delete an appointment."""
    success = db.delete(appointment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Afspraak niet gevonden.")
    return {"status": "deleted"}

# --- CONFIG REST API ---

@app.get("/api/config")
async def get_config():
    """Retrieve runtime settings."""
    return config.data

@app.post("/api/config")
async def update_config(data: Dict[str, Any]):
    """Update settings."""
    for key, value in data.items():
        config.set(key, value)
    return {"status": "saved", "config": config.data}

# --- SIMULATOR & TESTING REST API ---

@app.post("/api/simulate-call")
async def simulate_call(payload: Dict[str, str]):
    """Simulates an incoming telephone message turn."""
    user_text = payload.get("text", "")
    session_id = payload.get("session_id", "sim_session")
    
    intake = IntakeSession(session_id=session_id)
    intake.update_from_text(user_text, role="user")
    
    # Generate receptionist response
    system_prompt = get_receptionist_system_prompt()
    pipeline.set_system_prompt(system_prompt)
    pipeline.conversation_history.append({"role": "user", "content": user_text})
    
    token_generator = pipeline.llm.stream_chat(pipeline.conversation_history)
    agent_text = ""
    for token in token_generator:
        agent_text += token

    intake.update_from_text(agent_text, role="assistant")

    # If intake completed a booking, persist and dispatch
    booking_record = None
    if intake.is_complete_for_booking() or intake.status == "booking_confirmed":
        booking_data = intake.to_dict()
        booking_record = db.add(booking_data)
        NotificationDispatcher.dispatch_appointment(booking_record)

    return {
        "user_text": user_text,
        "agent_text": agent_text,
        "intake": intake.to_dict(),
        "booking_created": bool(booking_record),
        "booking": booking_record
    }

# --- WEBSOCKET LIVE AUDIO CALL STREAMING ---

@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    """
    Live Duplex WebSocket Telephone Audio & Transcript Session.
    Client -> Raw 16kHz PCM audio or control events.
    Server -> VAD state, ASR text, LLM chunks, Base64 Piper TTS WAV chunks.
    """
    await websocket.accept()
    intake = IntakeSession()
    system_prompt = get_receptionist_system_prompt()
    pipeline.reset_conversation(system_prompt)

    # Initial greeting in Dutch
    initial_greeting = config.get("business.greeting_nl", "Goedendag! Welkom, u spreekt met Sarah. Waarmee kan ik u helpen?")
    wav_bytes, sr = pipeline.tts.synthesize(initial_greeting, "nl")
    
    await websocket.send_json({
        "type": "agent_chunk",
        "text": initial_greeting,
        "language": "nl",
        "audio_base64": base64.b64encode(wav_bytes).decode("utf-8") if wav_bytes else None
    })

    audio_buffer = []

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                raw_bytes = message["bytes"]
                # Convert raw 16-bit PCM bytes to numpy array
                chunk_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Run Silero VAD
                prob, started, ended = pipeline.vad.process_chunk(chunk_np)
                audio_buffer.append(chunk_np)

                if started:
                    await websocket.send_json({"type": "vad_state", "is_speaking": True})

                if ended and len(audio_buffer) > 10:
                    await websocket.send_json({"type": "vad_state", "is_speaking": False})
                    full_utterance = np.concatenate(audio_buffer)
                    audio_buffer = []

                    # Process utterance turn
                    result = pipeline.process_speech_turn(full_utterance)
                    user_transcript = result.get("transcript", "")
                    lang = result.get("language", "nl")

                    if user_transcript:
                        intake.update_from_text(user_transcript, role="user")
                        await websocket.send_json({
                            "type": "user_transcript",
                            "text": user_transcript,
                            "language": lang,
                            "confidence": result.get("confidence", 1.0),
                            "intake": intake.to_dict()
                        })

                        # Stream synthesized agent chunks
                        audio_stream = result.get("audio_stream")
                        full_reply = ""
                        if audio_stream:
                            for chunk in audio_stream:
                                chunk_text = chunk["text"]
                                full_reply += chunk_text + " "
                                chunk_audio = chunk["wav_bytes"]
                                b64_audio = base64.b64encode(chunk_audio).decode("utf-8") if chunk_audio else None

                                await websocket.send_json({
                                    "type": "agent_chunk",
                                    "text": chunk_text,
                                    "language": lang,
                                    "audio_base64": b64_audio
                                })

                        intake.update_from_text(full_reply, role="assistant")
                        await websocket.send_json({"type": "intake_update", "intake": intake.to_dict()})

                        # Auto-confirm booking if criteria met
                        if intake.status == "booking_confirmed" or (intake.is_complete_for_booking() and not getattr(intake, "_booked", False)):
                            intake._booked = True
                            record = db.add(intake.to_dict())
                            NotificationDispatcher.dispatch_appointment(record)
                            await websocket.send_json({"type": "booking_confirmed", "appointment": record})

            elif "text" in message and message["text"]:
                # Text-based control or testing event
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "text_input":
                    user_text = data.get("text", "")
                    intake.update_from_text(user_text, role="user")
                    pipeline.conversation_history.append({"role": "user", "content": user_text})
                    
                    # Detect language heuristic
                    is_en = any(w in user_text.lower() for w in ["hello", "appointment", "schedule", "english", "please"])
                    lang = "en" if is_en else "nl"
                    
                    await websocket.send_json({
                        "type": "user_transcript",
                        "text": user_text,
                        "language": lang,
                        "intake": intake.to_dict()
                    })

                    token_gen = pipeline.llm.stream_chat(pipeline.conversation_history)
                    for chunk_text in pipeline.chunker.chunk_tokens(token_gen):
                        wav_bytes, sr = pipeline.tts.synthesize(chunk_text, lang)
                        b64_audio = base64.b64encode(wav_bytes).decode("utf-8") if wav_bytes else None
                        await websocket.send_json({
                            "type": "agent_chunk",
                            "text": chunk_text,
                            "language": lang,
                            "audio_base64": b64_audio
                        })

    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected from call session.")
    except Exception as e:
        print(f"[WebSocket] Error during call session: {e}")

def run_server():
    """Entry point for running uvicorn server."""
    import uvicorn
    host = config.get("server.host", "127.0.0.1")
    port = config.get("server.port", 8000)
    print(f"============================================================")
    print(f"  AI-Telefonist Engine Starting on http://{host}:{port}")
    print(f"  100% Offline Front-Desk • Dual-Language (NL / EN)")
    print(f"============================================================")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_server()
