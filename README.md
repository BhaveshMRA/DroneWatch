# DroneWatch 🛸
> Real-time multimodal vision AI — powered by Gemini Live API + A2A multi-agent architecture

**NYC Build With AI Hackathon — NYU Tandon School of Engineering | NYC Open Data Week 2026**
**Category: Live Agent**

---

## 🛑 The Problem

Urban environments generate massive amounts of visual data — traffic cameras, building feeds, drone footage — but analyzing them in real time typically requires expensive, highly specialized object-detection models trained on limited datasets.

**DroneWatch removes that barrier.** Point any camera at any scene. Gemini sees it, reasons about it, and speaks aloud — no training required.

---

## ✨ What It Does

DroneWatch is a multi-agent vision AI system where three specialized agents collaborate via an **Agent2Agent (A2A)** architecture to monitor a live camera feed and respond to natural voice questions in real time.

- **Vision Agent**: Watches the webcam, analyzes every frame using Gemini 2.5 Flash's native visual understanding, and broadcasts scene context.
- **NYC Data Agent**: Pulls live NYC Open Data traffic camera feeds and contextual city data.
- **Orchestrator Agent**: Receives raw PCM voice input from the browser, handles routing tasks across agents, and speaks back in real time using the **Gemini 3.1 Flash Live API** with full **Voice Activity Detection (VAD) and Barge-in** support.

No YOLO. No object detection models. No training datasets. Just pure multimodal reasoning.

---

## 🎤 Demo: Hold-to-Talk & Barge-in

```
[User points webcam at an emergency exit]

DroneWatch: "Clear. Two people detected center frame, no obstacles on the path—"

[User holds the mic button and interrupts mid-sentence]

User: "Wait, is there a fire alarm visible?"

DroneWatch: "Yes, I see a red fire alarm pull station on the right wall near the door."
```

This is **barge-in** and contextual awareness — the killer feature of the Gemini Live API. 

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT                      │
│   gemini-3.1-flash-live-preview (voice + VAD)       │
│   Receives PCM voice → checks vision → responses     │
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
     /.well-known/agent.json  ← A2A Agent Discovery Cards
```

Each agent runs as an independent service (FastAPI), communicating via the A2A protocol patterns. The React frontend uses an `AudioWorklet` to stream raw 16kHz PCM audio directly to the Orchestrator via WebSockets.

---

## 🏆 Hackathon Bonus Points Hit

| Requirement | Implementation |
|---|---|
| **Gemini 2.5 Flash** | Built-in `gemini-2.5-flash` for the Vision and Data agents |
| **Gemini Live API** | Integrated `gemini-3.1-flash-live-preview` (v1alpha) for zero-latency, full-duplex voice |
| **A2A Protocol** | Agents expose `/.well-known/agent.json` discovery cards and communicate laterally |
| **NYC Open Data** | Contextual live camera feeds + traffic data via NYC Open Data API |
| **Modern UX** | React + Vite frontend with glassmorphism UI, real-time event logs, and push-to-talk |

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| **Vision Reasoning** | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| **Voice + Barge-in** | Gemini Live API (`gemini-3.1-flash-live-preview`) |
| **GenAI Protocol** | `google-genai` Python SDK (v1alpha for Live sessions) |
| **Agent Communication**| A2A protocol (Agent2Agent) |
| **Backend & Routing** | Python, FastAPI, WebSockets |
| **Frontend UI/UX** | React, Vite, Canvas API, Web Audio API (AudioWorklet) |
| **City Data** | NYC Open Data REST API |

---

## 🚀 Setup & Run Locally

### 1. Requirements
Ensure you have Python 3.11+, Node.js, and a Gemini API Key.

### 2. Set API key
Create a `.env` file in the root directory:
```bash
GOOGLE_API_KEY=your_gemini_api_key_here
```

### 3. Run the Agents (in separate terminals)
```bash
# Terminal 1: Vision Agent (Port 8001)
cd agents/vision && python main.py

# Terminal 2: NYC Data Agent (Port 8002)
cd agents/nyc_data && python main.py

# Terminal 3: Orchestrator (Port 8000)
cd agents/orchestrator && python main.py
```

### 4. Run the Frontend (Port 5173)
```bash
# Terminal 4: React UI
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Grant microphone and camera permissions. Hold **HOLD TO TALK** to speak with the drone!

---

## 🏙️ NYC Open Data Integration

The NYC Data Agent is equipped to handle contextual queries about the environment:
- **DOT Traffic Cameras**: `data.cityofnewyork.us/resource/ecxy-mmzy.json`
- **Real-Time Traffic Speed**: `data.cityofnewyork.us/resource/i4gi-tjb9.json`
- **311 Incident Reports**: `data.cityofnewyork.us/resource/erm2-nwe9.json`

If Vision detects a crowd, NYC Data can automatically check for nearby incidents or traffic alerts.

---

## 🎯 Pitch Line

> *"Instead of training specialized detection models, DroneWatch gives any camera a brain it can talk to — and that brain talks back to the city."*

---

## 🛠️ Built At

**NYC Build With AI Hackathon 2026** · NYU Tandon School of Engineering · GDG NYC · NYC Open Data Week
