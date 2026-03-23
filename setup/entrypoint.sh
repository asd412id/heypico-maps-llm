#!/bin/bash
# Open WebUI entrypoint wrapper — runs original start.sh + auto-setup
# Starts Open WebUI normally, then registers tools in background

# Patch iframe sandbox to allow popups (for "Open in Google Maps" links)
sh /app/setup/patch-sandbox.sh

# Start Open WebUI (original entrypoint)
bash start.sh &
WEBUI_PID=$!

# Wait for API to be ready, then run setup
(
  echo "[setup] Waiting for Open WebUI to start..."
  for i in $(seq 1 100); do
    if curl -sf http://localhost:8080/api/config > /dev/null 2>&1; then
      echo "[setup] API ready, registering tools..."
      python /app/setup/setup-tools.py
      exit 0
    fi
    sleep 3
  done
  echo "[setup] Timeout waiting for API"
) &

# Wait for main process
wait $WEBUI_PID
