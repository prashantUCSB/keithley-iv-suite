#!/usr/bin/env bash
# ============================================================
# Keithley IV Suite — Linux Docker launcher
# Works with X11 and USB/GPIB VISA instruments.
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

# Allow container to connect to local X server
xhost +local:docker 2>/dev/null || true

# Build image if it doesn't exist
if ! docker image inspect keithley-iv-suite:latest &>/dev/null; then
    echo "[INFO] Building image..."
    docker build -t keithley-iv-suite:latest "$APP_DIR"
fi

echo "[INFO] Starting Keithley IV Suite..."

docker run --rm -it \
    -e DISPLAY="$DISPLAY" \
    -e XAUTHORITY="${XAUTHORITY:-}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    --device /dev/bus/usb \
    --network host \
    -v "$HOME/Documents/IV_Data:/root/Documents/IV_Data" \
    -v "$APP_DIR/recipes:/app/recipes:ro" \
    --name keithley-iv-suite \
    keithley-iv-suite:latest

# Revoke X access when done
xhost -local:docker 2>/dev/null || true
