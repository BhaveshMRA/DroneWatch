"""
DroneWatch Vision Agent — port 8001
Captures webcam frames via OpenCV, analyzes with Gemini 2.5 Flash,
streams alerts via WebSocket.
"""
import os
import cv2
import base64
import asyncio
import threading
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
VISION_MODEL = "gemini-2.5-flash"
FRAME_INTERVAL = 1.5  # seconds between Gemini analysis calls

SYSTEM_PROMPT = (
    "You are DroneWatch, a real-time vision AI co-pilot. "
    "Analyze the camera frame and respond in 1-2 sentences max. "
    "Use directional language: left, center, right. "
    "Start with ALERT: if any threat/hazard detected. "
    "Start with CLEAR: if scene is safe. "
    "Be specific. Never say you cannot see the image."
)

A2A_AGENT_CARD = {
    "name": "DroneWatch Vision Agent",
    "description": "Real-time webcam scene analysis using Gemini 2.5 Flash",
    "version": "1.0.0",
    "url": "http://localhost:8001",
    "capabilities": {"streaming": True, "vision": True},
    "endpoints": {"analyze": "/analyze", "stream": "/ws", "frame": "/frame"},
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
latest_frame_b64: Optional[str] = None
latest_alert: str = "CLEAR: Initializing DroneWatch vision system..."
frame_lock = threading.Lock()
alert_lock = threading.Lock()
active_websockets: list[WebSocket] = []
ws_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------
def get_genai_client():
    return genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

# ---------------------------------------------------------------------------
# Mock frame generator
# ---------------------------------------------------------------------------
def _generate_mock_frame():
    import numpy as np
    img = np.zeros((480, 640, 3), dtype="uint8")
    cv2.putText(img, "DroneWatch", (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 136), 3)
    cv2.putText(img, "Webcam Unavailable", (150, 280), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    ts = time.strftime("%H:%M:%S")
    cv2.putText(img, ts, (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
    return img

# ---------------------------------------------------------------------------
# Webcam capture thread
# ---------------------------------------------------------------------------
def webcam_capture_thread():
    global latest_frame_b64
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Webcam not available")
        cap.set(cv2.CAP_PROP_FPS, 30)
        logger.info("Webcam opened successfully")
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
            with frame_lock:
                latest_frame_b64 = b64
            time.sleep(1.0 / 30)
        cap.release()
    except Exception as exc:
        logger.warning(f"Webcam thread error: {exc} — using mock frames")
        while True:
            mock_img = _generate_mock_frame()
            _, buf = cv2.imencode(".jpg", mock_img)
            b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
            with frame_lock:
                latest_frame_b64 = b64
            time.sleep(1.0 / 30)

# ---------------------------------------------------------------------------
# Gemini analysis loop
# ---------------------------------------------------------------------------
async def analysis_loop():
    global latest_alert
    client = get_genai_client()
    while True:
        try:
            with frame_lock:
                b64 = latest_frame_b64
            if b64 and client:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=VISION_MODEL,
                    contents=[
                        types.Content(parts=[
                            types.Part(text=SYSTEM_PROMPT + "\n\nAnalyze this scene now."),
                            types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(b64))),
                        ])
                    ]
                )
                text = response.text.strip()
                with alert_lock:
                    latest_alert = text
                logger.info(f"Gemini: {text[:80]}")
                await broadcast_alert(text)
            elif b64 and not client:
                # No API key — return mock alert
                mock = "CLEAR: Vision system active. No API key configured — demo mode."
                with alert_lock:
                    latest_alert = mock
                await broadcast_alert(mock)
        except Exception as exc:
            logger.error(f"Analysis error: {exc}")
            fallback = "CLEAR: Vision system warming up. Stand by."
            with alert_lock:
                latest_alert = fallback
        await asyncio.sleep(FRAME_INTERVAL)

async def broadcast_alert(text: str):
    async with ws_lock:
        dead = []
        for ws in active_websockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            active_websockets.remove(ws)

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=webcam_capture_thread, daemon=True)
    t.start()
    time.sleep(0.5)
    task = asyncio.create_task(analysis_loop())
    logger.info("Vision Agent started on port 8001")
    yield
    task.cancel()

app = FastAPI(title="DroneWatch Vision Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/.well-known/agent.json")
async def agent_card():
    return A2A_AGENT_CARD

@app.get("/frame")
async def get_frame():
    with frame_lock:
        b64 = latest_frame_b64
    return {"frame": b64, "mime_type": "image/jpeg"}

@app.post("/analyze")
async def analyze():
    with alert_lock:
        text = latest_alert
    return {"text": text, "status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async with ws_lock:
        active_websockets.append(websocket)
    try:
        with alert_lock:
            current = latest_alert
        await websocket.send_text(current)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with ws_lock:
            if websocket in active_websockets:
                active_websockets.remove(websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
