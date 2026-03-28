#!/bin/bash

# Kill any running Python agents
echo "Killing existing agents..."
pkill -f "Python main.py" || true
sleep 1

# Load environment variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

echo "Starting Vision Agent (8001)..."
cd agents/vision

nohup python main.py > /tmp/vision.log 2>&1 &
cd ../..

echo "Starting NYC Data Agent (8002)..."
cd agents/nyc_data

nohup python main.py > /tmp/nyc.log 2>&1 &
cd ../..

echo "Starting Orchestrator Agent (8000)..."
cd agents/orchestrator

nohup python main.py > /tmp/orch.log 2>&1 &
cd ../..

echo "All agents started! Check logs:"
echo "tail -f /tmp/vision.log /tmp/nyc.log /tmp/orch.log"
