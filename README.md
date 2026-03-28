# DroneWatch 🛸
> Real-time multimodal vision AI — powered by Gemini Live API + A2A multi-agent architecture

**NYC Build With AI Hackathon — NYU Tandon School of Engineering | NYC Open Data Week 2026**
**Category: Live Agent**

---

## The Problem

Urban environments generate massive amounts of visual data — traffic cameras, building feeds, drone footage — but analyzing them in real time requires expensive, specialized object-detection models trained on specific datasets.

**DroneWatch removes that barrier.** Point any camera at any scene. Gemini sees it, reasons about it, and speaks aloud — no training required.

---

## What It Does

DroneWatch is a multi-agent vision AI system where three specialized agents collaborate via the **Agent2Agent (A2A) protocol** to monitor a live camera feed and respond to natural voice questions in real time.

- **Vision Agent** watches the webcam, analyzes every frame using Gemini's native visual understanding
- **NYC Data Agent** pulls live NYC Open Data traffic camera feeds and contextual city data
- **Orchestrator Agent** receives voice input, routes tasks across agents via A2A, and speaks back using Gemini Live API with barge-in support

No YOLO. No object detection models. No training datasets.

---

## Demo

```
[User points webcam at a scene]

Gemini: "Clear. Two people detected center frame, no obstacles on path—"

[User interrupts mid-sentence]

User: "What's behind the person on the left?"

Gemini: "A doorway, partially obstructed. Recommend caution if navigating."
```

This is **barge-in** — the killer feature of Gemini Live API. Judges can try it in 10 seconds.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT (ADK)                │
│   gemini-live-2.5-flash-preview (voice + barge-in)  │
│   Receives voice → routes tasks → speaks response   │
└──────────────────┬─────────────────┬────────────────┘
                   │  A2A protocol   │  A2A protocol
                   ▼                 ▼
     ┌─────────────────┐   ┌──────────────────────┐
     │  VISION AGENT   │   │   NYC DATA AGENT      │
     │  gemini-2.5-    │   │   gemini-2.5-flash    │
     │  flash          │   │                       │
     │                 │   │  NYC Open Data API    │
     │  Webcam frames  │   │  Live traffic cams    │
     │  Scene analysis │   │  Pedestrian counts    │
     │  Threat alerts  │   │  Incident reports     │
     └─────────────────┘   └──────────────────────┘
              │
     /.well-known/agent.json  ← A2A Agent Cards
```

Each agent runs as an independent service on **Google Cloud Run**, communicating via the A2A protocol.

---

## Bonus Points ✅

| Requirement | Implementation |
|---|---|
| **Gemini 2.5 Flash** | `gemini-2.5-flash` (all agents) |
| **Gemini Live API** | `gemini-live-2.5-flash-preview` (orchestrator voice) |
| **Google ADK** | Orchestrator built with Agent Development Kit |
| **A2A Protocol** | All agents expose `/.well-known/agent.json` + communicate via A2A |
| **Google Cloud Run** | Each agent deployed as independent Cloud Run service |
| **Gemini CLI** | Used for terminal-based scene analysis during demo |
| **NYC Open Data** | Live camera feeds + traffic data via NYC Open Data API |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Vision reasoning | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| Voice + barge-in | Gemini Live API (`gemini-live-2.5-flash-preview`) |
| Agent framework | Google ADK (Agent Development Kit) |
| Agent communication | A2A protocol (Agent2Agent) |
| Frame capture | OpenCV (webcam) |
| City data | NYC Open Data REST API |
| Backend | FastAPI + WebSockets |
| Frontend | React + Vite |
| Deploy | Google Cloud Run (3 services) |

---

## Project Structure

```
dronewatch/
├── agents/
│   ├── orchestrator/        # ADK orchestrator — voice + A2A client
│   │   ├── agent.py
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── vision/              # A2A server — webcam + Gemini vision
│   │   ├── agent.py
│   │   ├── main.py
│   │   └── Dockerfile
│   └── nyc_data/            # A2A server — NYC Open Data feeds
│       ├── agent.py
│       ├── main.py
│       └── Dockerfile
├── frontend/
│   └── src/App.jsx
├── backend.py               # Single-file quickstart (no Docker)
├── frontend.html            # Single-file quickstart UI
└── README.md
```

---

## Quickstart (Single File — No Docker)

### 1. Install
```bash
pip install google-genai opencv-python fastapi uvicorn websockets
```

### 2. Set API key
```bash
export GOOGLE_API_KEY=your_key_here
# Get free key → https://aistudio.google.com/app/apikey
```

### 3. Run
```bash
python backend.py
# Open frontend.html in browser
```

---

## Full Multi-Agent Setup (A2A + ADK)

### 1. Install ADK
```bash
pip install google-adk
```

### 2. Run Vision Agent (A2A Server — port 8001)
```bash
cd agents/vision && python main.py
# Agent card → http://localhost:8001/.well-known/agent.json
```

### 3. Run NYC Data Agent (A2A Server — port 8002)
```bash
cd agents/nyc_data && python main.py
# Agent card → http://localhost:8002/.well-known/agent.json
```

### 4. Run Orchestrator (ADK + A2A Client — port 8000)
```bash
cd agents/orchestrator && python main.py
```

### 5. Open frontend
```bash
cd frontend && npm install && npm run dev
```

---

## Deploy to Google Cloud Run

```bash
# Vision Agent
gcloud run deploy dronewatch-vision \
  --source ./agents/vision \
  --region us-central1 \
  --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY

# NYC Data Agent
gcloud run deploy dronewatch-nyc \
  --source ./agents/nyc_data \
  --region us-central1 \
  --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY

# Orchestrator
gcloud run deploy dronewatch-orchestrator \
  --source ./agents/orchestrator \
  --region us-central1 \
  --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY,\
VISION_AGENT_URL=https://dronewatch-vision-xxxx.run.app,\
NYC_AGENT_URL=https://dronewatch-nyc-xxxx.run.app
```

---

## NYC Open Data Integration

| Dataset | Endpoint |
|---|---|
| DOT Traffic Cameras | `data.cityofnewyork.us/resource/ecxy-mmzy.json` |
| Real-Time Traffic Speed | `data.cityofnewyork.us/resource/i4gi-tjb9.json` |
| 311 Incident Reports | `data.cityofnewyork.us/resource/erm2-nwe9.json` |

The NYC Data Agent surfaces this contextually — if Vision detects a crowd, NYC Data checks for nearby incidents or traffic alerts automatically.

---

## How A2A Works Here

1. Each agent publishes an **Agent Card** at `/.well-known/agent.json`
2. Orchestrator discovers agents by fetching their cards at startup
3. User asks *"What's the traffic like near here?"* → Orchestrator routes task to NYC Data Agent via A2A JSON-RPC
4. NYC Data Agent returns a structured artifact
5. Orchestrator combines with Vision output → speaks response via Gemini Live

Real agent interoperability — not a monolith pretending to be multi-agent.

---

## Pitch Line

> *"Instead of training specialized detection models, DroneWatch gives any camera a brain it can talk to — and that brain talks to the city."*

---

## Built At

NYC Build With AI Hackathon 2026 · NYU Tandon School of Engineering · GDG NYC · NYC Open Data Week
