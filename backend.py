"""
DroneWatch Backend — Single-file fallback (Vision only, no A2A, no ADK)
Run: python backend.py
Then open frontend.html in Chrome.
Port: 8000
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

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
VISION_MODEL   = "gemini-2.5-flash"
FRAME_INTERVAL = 1.5

SYSTEM_PROMPT = (
    "You are DroneWatch, a real-time vision AI co-pilot. "
    "Analyze the camera frame and respond in 1-2 sentences max. "
    "Use directional language: left, center, right. "
    "Start with ALERT: if any threat/hazard detected. "
    "Start with CLEAR: if scene is safe. "
    "Be specific. Never say you cannot see the image."
)

# State
latest_frame_b64: Optional[str] = None
latest_alert: str = "CLEAR: DroneWatch initializing..."
frame_lock  = threading.Lock()
alert_lock  = threading.Lock()
active_websockets: list[WebSocket] = []
ws_lock = asyncio.Lock()


def _generate_mock_frame():
    import numpy as np
    img = np.zeros((480, 640, 3), dtype="uint8")
    cv2.putText(img, "DroneWatch LIVE", (160, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 136), 3)
    cv2.putText(img, "Single-File Mode", (190, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
    ts = time.strftime("%H:%M:%S")
    cv2.putText(img, ts, (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
    return img


def webcam_thread():
    global latest_frame_b64
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("No webcam")
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64 = base64.b64encode(buf.tobytes()).decode()
            with frame_lock:
                latest_frame_b64 = b64
            time.sleep(1 / 30)
        cap.release()
    except Exception as exc:
        logger.warning(f"Webcam unavailable: {exc} — using mock")
        while True:
            mock = _generate_mock_frame()
            _, buf = cv2.imencode(".jpg", mock)
            b64 = base64.b64encode(buf.tobytes()).decode()
            with frame_lock:
                latest_frame_b64 = b64
            time.sleep(1 / 30)


async def analysis_loop():
    global latest_alert
    client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

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
                            types.Part(text=SYSTEM_PROMPT + "\n\nAnalyze this scene."),
                            types.Part(inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=base64.b64decode(b64),
                            )),
                        ])
                    ],
                )
                text = response.text.strip()
                with alert_lock:
                    latest_alert = text
                await broadcast(text)
            elif b64 and not client:
                mock = "CLEAR: Vision active — no API key (demo mode)."
                with alert_lock:
                    latest_alert = mock
                await broadcast(mock)
        except Exception as exc:
            logger.error(f"Gemini: {exc}")
        await asyncio.sleep(FRAME_INTERVAL)


async def broadcast(text: str):
    async with ws_lock:
        dead = []
        for ws in active_websockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            active_websockets.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=webcam_thread, daemon=True)
    t.start()
    time.sleep(0.5)
    task = asyncio.create_task(analysis_loop())
    logger.info("DroneWatch backend running on http://localhost:8000")
    yield
    task.cancel()


app = FastAPI(title="DroneWatch Backend", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/frame")
async def frame():
    with frame_lock:
        b64 = latest_frame_b64
    return {"frame": b64, "mime_type": "image/jpeg"}

@app.get("/alert")
async def alert():
    with alert_lock:
        text = latest_alert
    return {"text": text}

@app.post("/analyze")
async def analyze():
    with alert_lock:
        text = latest_alert
    return {"text": text, "status": "ok"}

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    async with ws_lock:
        active_websockets.append(websocket)
    try:
        with alert_lock:
            await websocket.send_text(latest_alert)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        pass
    finally:
        async with ws_lock:
            if websocket in active_websockets:
                active_websockets.remove(websocket)


if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=False)
