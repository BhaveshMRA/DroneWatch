"""
DroneWatch Orchestrator Agent — port 8000
Built with Google ADK-style LlmAgent pattern.
Uses screenshot-based voice: POST /voice-ask accepts audio+frame multipart, transcribes
via Gemini, and returns a JSON text response (no Live API required).
Routes tasks to Vision (8001) and NYC Data (8002) via A2A.
Uses new google.genai SDK (v1.x).
"""
import os
import asyncio
import logging
import json
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY", "")
VISION_AGENT_URL  = os.environ.get("VISION_AGENT_URL", "http://localhost:8001")
NYC_AGENT_URL     = os.environ.get("NYC_AGENT_URL", "http://localhost:8002")
ADK_MODEL         = "gemini-2.5-flash"  # stable text/tool-call model

ADK_INSTRUCTION = (
    "You are DroneWatch, an AI surveillance co-pilot. "
    "You have two tools: analyze_scene() and get_city_data(). "
    "For visual questions: call analyze_scene(). "
    "For city/traffic questions: call get_city_data(). "
    "For combined questions: call both. "
    "Be concise. Speak like a calm, professional operator."
)

A2A_AGENT_CARD = {
    "name": "DroneWatch Orchestrator Agent",
    "description": "ADK orchestrator — voice + A2A routing to Vision and NYC Data agents",
    "version": "1.0.0",
    "url": "http://localhost:8000",
    "capabilities": {"streaming": True, "voice": True, "orchestrator": True},
    "endpoints": {"voice_ask": "/voice-ask", "status": "/status", "alert": "/alert", "stream": "/ws"},
    "agents": {"vision": VISION_AGENT_URL, "nyc_data": NYC_AGENT_URL},
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
vision_status = "connecting"
nyc_status    = "connecting"
vision_card: dict = {}
nyc_card: dict = {}
active_text_sockets: list[WebSocket] = []
ws_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# A2A calls to sub-agents
# ---------------------------------------------------------------------------
async def analyze_scene() -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{VISION_AGENT_URL}/analyze")
            return resp.json().get("text", "Scene analysis unavailable.")
    except Exception as exc:
        logger.error(f"Vision error: {exc}")
        return "CLEAR: Scene analysis temporarily unavailable."

async def get_city_data(question: str = "What is the current traffic situation?") -> str:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(f"{NYC_AGENT_URL}/query", json={"question": question})
            return resp.json().get("answer", "NYC data unavailable.")
    except Exception as exc:
        logger.error(f"NYC error: {exc}")
        return "NYC traffic data temporarily unavailable."

# ---------------------------------------------------------------------------
# ADK-style LLM agent with function calling
# ---------------------------------------------------------------------------
async def run_adk_agent(user_message: str) -> str:
    if not GOOGLE_API_KEY:
        return "API key not configured."

    client = genai.Client(api_key=GOOGLE_API_KEY)

    tools = [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="analyze_scene",
                description="Analyze the current webcam scene using the Vision Agent.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_city_data",
                description="Get live NYC city and traffic data.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "question": types.Schema(
                            type=types.Type.STRING,
                            description="The question about NYC city data.",
                        )
                    },
                ),
            ),
        ])
    ]

    config = types.GenerateContentConfig(
        system_instruction=ADK_INSTRUCTION,
        tools=tools,
    )

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=ADK_MODEL,
            contents=user_message,
            config=config,
        )

        all_results = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                if fc.name == "analyze_scene":
                    result = await analyze_scene()
                    all_results.append(f"[Vision]: {result}")
                elif fc.name == "get_city_data":
                    question = fc.args.get("question", "traffic situation") if fc.args else "traffic"
                    result = await get_city_data(question)
                    all_results.append(f"[NYC Data]: {result}")

        if all_results:
            combined = "\n".join(all_results)
            followup = [
                types.Content(role="user", parts=[types.Part(text=user_message)]),
                response.candidates[0].content,
                types.Content(role="user", parts=[types.Part(
                    text=f"Tool results:\n{combined}\n\nRespond naturally to the user's query."
                )]),
            ]
            final = await asyncio.to_thread(
                client.models.generate_content,
                model=ADK_MODEL,
                contents=followup,
                config=types.GenerateContentConfig(system_instruction=ADK_INSTRUCTION),
            )
            return final.text.strip()

        return response.text.strip()

    except Exception as exc:
        logger.error(f"ADK agent error: {exc}")
        return f"System error: {str(exc)[:100]}"

# ---------------------------------------------------------------------------
# A2A Agent Card discovery
# ---------------------------------------------------------------------------
async def discover_agent_cards():
    """Fetch /.well-known/agent.json from each sub-agent (real A2A discovery)."""
    global vision_card, nyc_card
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{VISION_AGENT_URL}/.well-known/agent.json")
            vision_card = r.json()
            logger.info(f"A2A discovered Vision Agent: {vision_card.get('name')}")
        except Exception as exc:
            logger.warning(f"Could not discover Vision Agent card: {exc}")
        try:
            r = await client.get(f"{NYC_AGENT_URL}/.well-known/agent.json")
            nyc_card = r.json()
            logger.info(f"A2A discovered NYC Data Agent: {nyc_card.get('name')}")
        except Exception as exc:
            logger.warning(f"Could not discover NYC Data Agent card: {exc}")

# ---------------------------------------------------------------------------
# Status monitor
# ---------------------------------------------------------------------------
async def check_agent_statuses():
    global vision_status, nyc_status
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            r = await client.get(f"{VISION_AGENT_URL}/health")
            vision_status = "ok" if r.status_code == 200 else "error"
        except Exception:
            vision_status = "error"
        try:
            r = await client.get(f"{NYC_AGENT_URL}/health")
            nyc_status = "ok" if r.status_code == 200 else "error"
        except Exception:
            nyc_status = "error"
    logger.info(f"Status — vision: {vision_status}, nyc: {nyc_status}")

async def status_monitor():
    while True:
        await check_agent_statuses()
        await asyncio.sleep(15)

async def broadcast_text(text: str):
    async with ws_lock:
        dead = []
        for ws in active_text_sockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            active_text_sockets.remove(ws)

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await discover_agent_cards()   # real A2A discovery
    await check_agent_statuses()
    task = asyncio.create_task(status_monitor())
    logger.info("Orchestrator Agent started on port 8000")
    yield
    task.cancel()

app = FastAPI(title="DroneWatch Orchestrator Agent", lifespan=lifespan)
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

@app.get("/status")
async def status():
    return {
        "vision": vision_status,
        "nyc": nyc_status,
        "voice": "ready",
        "agents": {
            "vision": vision_card.get("name", "unknown"),
            "nyc_data": nyc_card.get("name", "unknown"),
        },
    }

@app.get("/alert")
async def get_alert():
    try:
        text = await analyze_scene()
        return {"text": text, "status": "ok"}
    except Exception as exc:
        return {"text": "CLEAR: System initializing.", "status": "error", "error": str(exc)}

@app.post("/voice-ask")
async def voice_ask(audio: UploadFile = File(...)):
    """
    Hold-to-Talk endpoint.
    Receives a WebM/OGG audio blob from the browser.
    1. Transcribes the audio with gemini-2.5-flash
    2. Fetches the current camera frame from the Vision Agent
    3. Sends frame + transcript to gemini-2.5-flash for a multimodal answer
    Returns: { transcript, text }
    """
    if not GOOGLE_API_KEY:
        return JSONResponse({"error": "GOOGLE_API_KEY not configured"}, status_code=500)

    client = genai.Client(api_key=GOOGLE_API_KEY)
    audio_bytes = await audio.read()
    mime = audio.content_type or "audio/webm"

    # --- Step 1: Transcribe audio ---
    try:
        transcription_response = await asyncio.to_thread(
            client.models.generate_content,
            model=ADK_MODEL,
            contents=[
                types.Content(parts=[
                    types.Part(text="Transcribe this audio exactly as spoken. Return only the spoken words, nothing else."),
                    types.Part(inline_data=types.Blob(mime_type=mime, data=audio_bytes)),
                ])
            ],
        )
        transcript = transcription_response.text.strip()
        logger.info(f"Transcript: {transcript}")
    except Exception as exc:
        logger.error(f"Transcription error: {exc}")
        transcript = "What do you see?"

    # --- Step 2: Fetch current camera frame ---
    frame_b64 = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as http:
            frame_resp = await http.get(f"{VISION_AGENT_URL}/frame")
            frame_b64 = frame_resp.json().get("frame")
    except Exception as exc:
        logger.warning(f"Could not fetch frame: {exc}")

    # --- Step 3: Multimodal answer ---
    try:
        parts = [
            types.Part(text=(
                f"You are DroneWatch, an AI surveillance co-pilot. "
                f"The user asked: \"{transcript}\"\n"
                f"The attached image is the current live camera view. "
                f"Answer concisely in 1-3 sentences based on what you see."
            ))
        ]
        if frame_b64:
            import base64
            parts.append(types.Part(inline_data=types.Blob(
                mime_type="image/jpeg",
                data=base64.b64decode(frame_b64),
            )))

        answer_response = await asyncio.to_thread(
            client.models.generate_content,
            model=ADK_MODEL,
            contents=[types.Content(parts=parts)],
        )
        answer = answer_response.text.strip()
        logger.info(f"Answer: {answer}")
    except Exception as exc:
        logger.error(f"Answer error: {exc}")
        answer = "I'm having trouble analyzing the scene right now."

    # Broadcast to any connected text sockets too
    await broadcast_text(f"[Voice AI]: {answer}")

    return {"transcript": transcript, "text": answer}

@app.websocket("/ws")
async def text_websocket(websocket: WebSocket):
    await websocket.accept()
    async with ws_lock:
        active_text_sockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"WS query: {data[:80]}")
            response = await run_adk_agent(data)
            await websocket.send_text(response)
            await broadcast_text(response)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(f"WS error: {exc}")
    finally:
        async with ws_lock:
            if websocket in active_text_sockets:
                active_text_sockets.remove(websocket)

@app.post("/voice-ask")
async def voice_ask(
    audio: UploadFile = File(...),
):
    """
    Screenshot-based voice endpoint.
    Accepts a multipart audio file (WebM/OGG from MediaRecorder).
    Steps:
      1. Transcribe audio via Gemini inline_data
      2. Fetch current frame from Vision Agent
      3. Ask Gemini with transcript + frame image
      4. Return { text, transcript }
    """
    if not GOOGLE_API_KEY:
        return {"error": "GOOGLE_API_KEY not set", "text": "", "transcript": ""}

    client = genai.Client(api_key=GOOGLE_API_KEY)

    # ---- Step 1: Read audio bytes ----
    audio_bytes = await audio.read()
    audio_mime = audio.content_type or "audio/webm"
    logger.info(f"voice-ask: received {len(audio_bytes)} bytes of {audio_mime}")

    # ---- Step 2: Transcribe with Gemini ----
    transcript = ""
    try:
        transcribe_response = await asyncio.to_thread(
            client.models.generate_content,
            model=ADK_MODEL,
            contents=[
                types.Part(
                    inline_data=types.Blob(mime_type=audio_mime, data=audio_bytes)
                ),
                types.Part(text="Transcribe the spoken words in this audio clip. Return ONLY the transcription, no extra commentary."),
            ],
        )
        transcript = transcribe_response.text.strip()
        logger.info(f"Transcription: {transcript[:120]}")
    except Exception as exc:
        logger.error(f"Transcription error: {exc}")
        transcript = "(could not transcribe audio)"

    # ---- Step 3: Fetch camera frame ----
    frame_b64 = None
    try:
        async with httpx.AsyncClient(timeout=4.0) as hclient:
            r = await hclient.get(f"{VISION_AGENT_URL}/frame")
            frame_b64 = r.json().get("frame")
    except Exception as exc:
        logger.warning(f"Could not fetch camera frame: {exc}")

    # ---- Step 4: Ask Gemini with optional frame ----
    contents = []
    if frame_b64:
        import base64
        contents.append(types.Part(
            inline_data=types.Blob(
                mime_type="image/jpeg",
                data=base64.b64decode(frame_b64),
            )
        ))
    contents.append(types.Part(text=(
        f"The user asked (via voice): {transcript}\n\n"
        "You are DroneWatch, an AI drone surveillance co-pilot. "
        "If an image of the camera view is provided, describe what you see. "
        "Be concise and professional, like a calm surveillance operator."
    )))

    try:
        answer_response = await asyncio.to_thread(
            client.models.generate_content,
            model=ADK_MODEL,
            contents=contents,
        )
        answer = answer_response.text.strip()
    except Exception as exc:
        logger.error(f"Gemini answer error: {exc}")
        answer = f"System error: {str(exc)[:100]}"

    logger.info(f"voice-ask answer: {answer[:120]}")
    return {"text": answer, "transcript": transcript}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
