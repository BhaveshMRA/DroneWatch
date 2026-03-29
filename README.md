# DroneWatch by Bhavesh Maurya & Kumar Saurabh 🛸
> Real-time multimodal vision AI — powered by Gemini 2.5 Flash + A2A multi-agent architecture

**NYC Build With AI Hackathon — NYU Tandon School of Engineering | NYC Open Data Week 2026**
**Category: Live Agent**

---

## 🛑 The Problem

Urban environments generate massive amounts of visual data — traffic cameras, building feeds, drone footage — but analyzing them in real time typically requires expensive, highly specialized object-detection models trained on limited datasets.

**DroneWatch removes that barrier.** Point any camera at any scene. Gemini sees it, reasons about it, and speaks aloud — no training required.

---

## ✨ What It Does

DroneWatch is a multi-agent vision AI system where three specialized agents collaborate via an **Agent2Agent (A2A)** architecture to monitor a live camera feed and respond to natural voice questions in real time.

- **Vision Agent**: Watches the webcam, analyzes every frame using Gemini 2.5 Flash's native visual understanding, and broadcasts scene context via WebSocket alerts.
- **NYC Data Agent**: Pulls live NYC Open Data traffic camera feeds and contextual city data.
- **Orchestrator Agent**: Receives voice recordings from the browser, transcribes them, fetches the current camera frame, and asks Gemini 2.5 Flash with both the transcript and the image — returning a spoken response via the browser's Web Speech API.

No YOLO. No object detection models. No training datasets. Just pure multimodal reasoning.

---

## 🎤 Demo: Hold-to-Talk Voice Interaction

```
[User points webcam at a busy street]

User holds the HOLD TO TALK button and asks:
  "What's happening in the center of the frame?"

DroneWatch:
  "CLEAR: Two pedestrians are visible center-frame walking
   towards the camera. No hazards detected."
```

**How it works:**
1. Hold the **HOLD TO TALK** button → browser starts recording via `MediaRecorder`
2. Release → audio blob is POSTed to `POST /voice-ask` on the Orchestrator
3. Orchestrator transcribes audio via Gemini, fetches the live camera frame
4. Gemini 2.5 Flash reasons over the transcript + image
5. Response is spoken aloud via the browser's **Web Speech API**

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT  (port 8000)         │
│   POST /voice-ask → transcribe + frame → Gemini     │
│   WebSocket /ws   → text query routing              │
└──────────────────┬─────────────────┬────────────────┘
                   │  A2A protocol   │  A2A protocol
                   ▼                 ▼
     ┌─────────────────┐   ┌──────────────────────┐
     │  VISION AGENT   │   │   NYC DATA AGENT      │
     │  (port 8001)    │   │   (port 8002)         │
     │  gemini-2.5-    │   │   gemini-2.5-flash    │
     │  flash          │   │                       │
     │  Webcam frames  │   │  NYC Open Data API    │
     │  Scene analysis │   │  Live traffic cams    │
     │  Threat alerts  │   │  Incident reports     │
     └─────────────────┘   └──────────────────────┘
              │
     /.well-known/agent.json  ← A2A Agent Discovery Cards
```

```text
VOICE PIPELINE (frontend → orchestrator):

  [Hold button] → MediaRecorder captures WebM audio
  [Release]     → POST /voice-ask (multipart: audio blob)
  Orchestrator  → transcribe via Gemini inline_data
                → fetch /frame from Vision Agent
                → Gemini 2.5 Flash (transcript + image)
                → return { text, transcript }
  Frontend      → SpeechSynthesis.speak(text)
                → show transcript in Event Log
```

Each agent runs as an independent FastAPI service, communicating via A2A protocol patterns.

---

## 🏆 Hackathon Bonus Points Hit

| Requirement | Implementation |
|---|---|
| **Gemini 2.5 Flash** | `gemini-2.5-flash` for Vision, Orchestrator voice, and NYC Data agents |
| **A2A Protocol** | Agents expose `/.well-known/agent.json` discovery cards and communicate laterally |
| **NYC Open Data** | Contextual live camera feeds + traffic data via NYC Open Data API |
| **Multimodal Voice** | Audio transcription + live camera frame combined in a single Gemini call |
| **Modern UX** | React + Vite frontend with real-time HUD, event logs, and push-to-talk |

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| **Vision Reasoning** | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| **Voice Transcription** | Gemini 2.5 Flash inline audio → text |
| **Voice Synthesis** | Browser Web Speech API (`SpeechSynthesis`) |
| **GenAI SDK** | `google-genai` Python SDK |
| **Agent Communication** | A2A protocol (Agent2Agent) |
| **Backend & Routing** | Python, FastAPI, WebSockets |
| **Frontend UI/UX** | React, Vite, MediaRecorder API |
| **City Data** | NYC Open Data REST API |

---

## 🚀 Setup & Run Locally

### 1. Requirements
Ensure you have Python 3.11+, Node.js 18+, and a Gemini API Key.

### 2. Set API Key
Create a `.env` file (or export before running agents):
```bash
export GOOGLE_API_KEY=your_gemini_api_key_here
```
> ⚠️ The API key must be set in the **same terminal** before starting each agent — it is read at startup.

### 3. Run the Agents (in separate terminals)
```bash
# Terminal 1: Vision Agent (Port 8001)
cd agents/vision && GOOGLE_API_KEY=your_key python main.py

# Terminal 2: NYC Data Agent (Port 8002)  [optional]
cd agents/nyc_data && GOOGLE_API_KEY=your_key python main.py

# Terminal 3: Orchestrator (Port 8000)
cd agents/orchestrator && GOOGLE_API_KEY=your_key python main.py
```

### 4. Run the Frontend (Port 5173)
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — grant microphone & camera permissions, then hold **HOLD TO TALK** to speak with the drone!

---

## 🏙️ NYC Open Data Integration

The NYC Data Agent handles contextual queries about the environment:
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
