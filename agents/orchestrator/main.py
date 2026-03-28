"""
DroneWatch Orchestrator Agent — port 8000
Built with Google ADK-style LlmAgent pattern.
Uses Gemini Live API (gemini-live-2.5-flash-preview) for real-time voice with barge-in.
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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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
LIVE_MODEL        = "gemini-3.1-flash-live-preview"  # latest Live model (bidiGenerateContent)
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
    "endpoints": {"voice": "/voice", "status": "/status", "alert": "/alert", "stream": "/ws"},
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

@app.websocket("/voice")
async def voice_websocket(websocket: WebSocket):
    """
    Voice WebSocket — Push-to-talk with Gemini Live API.
    Uses send_realtime_input for audio which relies on server-side VAD.
    IMPORTANT: Do NOT mix send_realtime_input with send_client_content(turn_complete)
    — they use different turn management modes and mixing causes 1007 errors.
    """
    await websocket.accept()
    logger.info("Voice WebSocket connected")

    if not GOOGLE_API_KEY:
        await websocket.send_text(json.dumps({"error": "GOOGLE_API_KEY not set"}))
        await websocket.close()
        return

    client = genai.Client(
        api_key=GOOGLE_API_KEY,
        http_options={"api_version": "v1alpha"},
    )

    # Fetch current scene context so Gemini knows what the camera sees
    scene_text = "No context available."
    try:
        scene_text = await analyze_scene()
        logger.info(f"Fetched scene context: {scene_text[:80]}")
    except Exception as exc:
        logger.warning(f"Could not fetch scene context: {exc}")

    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=f"""You are DroneWatch, an AI drone surveillance co-pilot. 
CRITICAL RULE: NEVER say you do not have visual capabilities. The system is feeding you the live camera view as text directly into this prompt. 
When asked what you see, describe the scene EXACTLY as provided in the [Current camera view] data below. Be concise, professional, and confident, like a surveillance operator.

[Current camera view]: {scene_text}""",
    )

    ws_open = True

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=live_config) as session:
            logger.info(f"Gemini Live session opened — model={LIVE_MODEL}")

            async def send_audio():
                nonlocal ws_open
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            logger.info("Client released button — closing send loop")
                            ws_open = False
                            break
                        if "bytes" in msg and msg["bytes"]:
                            # Raw PCM Int16 from AudioWorklet — 16kHz mono
                            # Server-side VAD handles turn detection automatically
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    mime_type="audio/pcm;rate=16000",
                                    data=msg["bytes"],
                                )
                            )
                except WebSocketDisconnect:
                    logger.info("WS disconnected in send loop")
                    ws_open = False
                except Exception as exc:
                    logger.error(f"Audio send error: {exc}")
                    ws_open = False

            async def receive_responses():
                try:
                    async for response in session.receive():
                        if not ws_open:
                            continue
                        # Path 1 — direct audio blob
                        if hasattr(response, "data") and response.data:
                            logger.info(f"Gemini audio chunk: {len(response.data)} bytes")
                            try:
                                await websocket.send_bytes(response.data)
                            except Exception:
                                break
                            continue
                        # Path 2 — server_content → model_turn → parts
                        sc = getattr(response, "server_content", None)
                        if sc:
                            mt = getattr(sc, "model_turn", None)
                            if mt:
                                for part in getattr(mt, "parts", []):
                                    inline = getattr(part, "inline_data", None)
                                    if inline and getattr(inline, "data", None):
                                        try:
                                            await websocket.send_bytes(inline.data)
                                        except Exception:
                                            break
                                    txt = getattr(part, "text", None)
                                    if txt:
                                        logger.info(f"Transcript: {txt[:80]}")
                                        try:
                                            await websocket.send_text(
                                                json.dumps({"type": "transcript", "text": txt})
                                            )
                                        except Exception:
                                            break
                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    # 1007 on session teardown is expected — don't log as error
                    err_str = str(exc)
                    if "1007" in err_str:
                        logger.info(f"Gemini Live session closed (1007 — normal teardown)")
                    else:
                        logger.error(f"Audio receive error: {type(exc).__name__}: {exc}")

            await asyncio.gather(send_audio(), receive_responses())

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(f"Live session error: {type(exc).__name__}: {exc}")
        try:
            await websocket.send_text(json.dumps({"error": str(exc)}))
        except Exception:
            pass
    finally:
        logger.info("Voice WebSocket disconnected")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
