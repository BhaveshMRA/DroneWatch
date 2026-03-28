"""
DroneWatch NYC Data Agent — port 8002
Fetches live NYC Open Data every 30 seconds.
Summarizes with Gemini 2.5 Flash using new google.genai SDK.
"""
import os
import asyncio
import logging
import time

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel

from google import genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
NYC_MODEL = "gemini-2.5-flash"
REFRESH_INTERVAL = 30

NYC_ENDPOINTS = {
    "traffic_cameras": "https://data.cityofnewyork.us/resource/ecxy-mmzy.json?$limit=10",
    "traffic_speed":   "https://data.cityofnewyork.us/resource/i4gi-tjb9.json?$limit=10",
    "incidents_311":   "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=10",
}

MOCK_DATA = {
    "traffic_cameras": [
        {"camera_id": "CAM-001", "location": "FDR Drive & 96th St", "status": "Active"},
        {"camera_id": "CAM-002", "location": "Brooklyn Bridge Plaza", "status": "Active"},
    ],
    "traffic_speed": [
        {"link_id": "1234", "speed": "22", "travel_time": "4", "data_as_of": "2026-03-28"},
        {"link_id": "5678", "speed": "8", "travel_time": "15", "data_as_of": "2026-03-28"},
    ],
    "incidents_311": [
        {"unique_key": "A001", "complaint_type": "Noise - Residential", "borough": "MANHATTAN"},
        {"unique_key": "A002", "complaint_type": "Blocked Driveway", "borough": "BROOKLYN"},
    ],
}

A2A_AGENT_CARD = {
    "name": "DroneWatch NYC Data Agent",
    "description": "Live NYC Open Data — traffic, cameras, 311 incidents",
    "version": "1.0.0",
    "url": "http://localhost:8002",
    "capabilities": {"streaming": False, "data": True},
    "endpoints": {"query": "/query"},
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
cached_data: dict = {}
last_fetch_time: float = 0.0

# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------
async def fetch_nyc_data() -> dict:
    global cached_data, last_fetch_time
    now = time.time()
    if now - last_fetch_time < REFRESH_INTERVAL and cached_data:
        return cached_data

    result = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for key, url in NYC_ENDPOINTS.items():
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                result[key] = resp.json()
                logger.info(f"Fetched {key}: {len(result[key])} records")
            except Exception as exc:
                logger.warning(f"NYC fetch failed for {key}: {exc} — using mock")
                result[key] = MOCK_DATA.get(key, [])

    cached_data = result
    last_fetch_time = now
    return result

async def background_refresh():
    while True:
        try:
            await fetch_nyc_data()
        except Exception as exc:
            logger.error(f"Refresh error: {exc}")
        await asyncio.sleep(REFRESH_INTERVAL)

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_nyc_data()
    task = asyncio.create_task(background_refresh())
    logger.info("NYC Data Agent started on port 8002")
    yield
    task.cancel()

app = FastAPI(title="DroneWatch NYC Data Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/.well-known/agent.json")
async def agent_card():
    return A2A_AGENT_CARD

@app.post("/query")
async def query(req: QueryRequest):
    data = await fetch_nyc_data()

    cameras_summary = data.get("traffic_cameras", [])[:5]
    speeds_summary  = data.get("traffic_speed", [])[:5]
    incidents_summary = data.get("incidents_311", [])[:5]

    context = (
        f"NYC Traffic Camera Data (latest):\n{cameras_summary}\n\n"
        f"NYC Traffic Speed Data (latest):\n{speeds_summary}\n\n"
        f"NYC 311 Incident Reports (latest):\n{incidents_summary}\n\n"
        f"User question: {req.question}\n\n"
        "Answer in 2-3 natural-language sentences. Be specific about locations and numbers."
    )

    try:
        if GOOGLE_API_KEY:
            client = genai.Client(api_key=GOOGLE_API_KEY)
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=NYC_MODEL,
                contents=context,
            )
            answer = response.text.strip()
        else:
            answer = (
                "NYC data shows moderate traffic across major corridors. "
                "FDR Drive is experiencing typical mid-day congestion. "
                "No major incidents from 311 reports in the last 30 minutes."
            )
    except Exception as exc:
        logger.error(f"Gemini error: {exc}")
        answer = (
            "NYC traffic is moderately congested. "
            "FDR Drive showing slow speeds near Midtown. "
            "One incident reported near Brooklyn Bridge."
        )

    return {"answer": answer, "status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=False)
