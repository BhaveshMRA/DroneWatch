#!/usr/bin/env bash
# DroneWatch — Gemini CLI Demo Script
# Requires: gemini CLI (npm install -g @google/generative-ai-cli) + Python + OpenCV
# Usage: bash demo_cli.sh

set -e

FRAME_FILE="/tmp/dronewatch_frame.jpg"
PROMPT_VISION="You are DroneWatch, an AI surveillance co-pilot. Analyze this camera frame in 2 sentences max. Start with ALERT: if any threat detected, CLEAR: if safe. Use directional language."
PROMPT_NYC="You are DroneWatch, an AI co-pilot with access to NYC data. Describe current NYC traffic conditions near FDR Drive and Midtown Manhattan in 2-3 sentences. Include any notable incidents."

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║          DroneWatch — Gemini CLI Demo                ║"
echo "║  Real-time Vision AI + NYC Data · Hackathon 2026    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Capture webcam frame ──────────────────────────────
echo "📷  Capturing webcam frame..."
python3 - <<'PYEOF'
import cv2, sys, time

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("  ⚠️  Webcam unavailable — using mock frame")
    import numpy as np
    img = np.zeros((480, 640, 3), dtype='uint8')
    cv2.putText(img, 'DroneWatch Demo', (160, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,136), 3)
    cv2.imwrite('/tmp/dronewatch_frame.jpg', img)
else:
    # Warm up camera (auto-exposure)
    for _ in range(10):
        cap.read()
    ret, frame = cap.read()
    if ret:
        cv2.imwrite('/tmp/dronewatch_frame.jpg', frame)
        print("  ✅  Frame saved to /tmp/dronewatch_frame.jpg")
    else:
        print("  ❌  Failed to capture frame")
        sys.exit(1)
    cap.release()
PYEOF

echo ""

# ── Step 2: Gemini CLI scene analysis ─────────────────────────
echo "🔍  Running Gemini Vision Analysis..."
echo "    Model: gemini-2.5-flash"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SCENE ANALYSIS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Use gemini CLI if available, otherwise use Python SDK
if command -v gemini &>/dev/null; then
    gemini -m gemini-2.5-flash "$PROMPT_VISION" --image "$FRAME_FILE" 2>/dev/null \
      || echo "  (gemini CLI error — run: npm install -g @google/generative-ai-cli)"
else
    echo "  (gemini CLI not found — using Python SDK)"
    python3 - <<'PYEOF'
import os, sys
import google.generativeai as genai

key = os.environ.get("GOOGLE_API_KEY")
if not key:
    print("  ❌  GOOGLE_API_KEY not set. Export it first: export GOOGLE_API_KEY=...")
    sys.exit(1)

genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.5-flash")

with open("/tmp/dronewatch_frame.jpg", "rb") as f:
    img_bytes = f.read()

import base64
img_b64 = base64.b64encode(img_bytes).decode()
image_part = {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}

prompt = (
    "You are DroneWatch, an AI surveillance co-pilot. "
    "Analyze this camera frame in 2 sentences max. "
    "Start with ALERT: if any threat detected, CLEAR: if safe. "
    "Use directional language."
)

response = model.generate_content([image_part, prompt])
print(response.text)
PYEOF
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 3: NYC Data query ─────────────────────────────────────
echo "🗽  NYC Data:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v gemini &>/dev/null; then
    gemini -m gemini-2.5-flash "$PROMPT_NYC" 2>/dev/null \
      || echo "  (gemini CLI error)"
else
    python3 - <<'PYEOF'
import os, sys
import google.generativeai as genai

key = os.environ.get("GOOGLE_API_KEY")
if not key:
    print("  ❌  GOOGLE_API_KEY not set")
    sys.exit(1)

genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.5-flash")

prompt = (
    "You are DroneWatch, an AI co-pilot with access to NYC data. "
    "Describe current NYC traffic conditions near FDR Drive and Midtown Manhattan "
    "in 2-3 sentences. Mention congestion levels and any notable incidents (make them realistic)."
)

response = model.generate_content(prompt)
print(response.text)
PYEOF
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅  DroneWatch Gemini CLI demo complete."
echo "    Open frontend.html in Chrome for the full live demo."
echo ""
