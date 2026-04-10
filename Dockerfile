# ============================================================
# Keithley IV Suite v2.0.0 — Linux Docker Image
#
# TARGET PLATFORM: Linux host (Ubuntu/Debian/Fedora)
# GUI: X11 forwarding ($DISPLAY + /tmp/.X11-unix from host)
# VISA: pyvisa-py bundled (no NI-VISA needed)
#       USB instruments: requires --device /dev/bus/usb
#       Ethernet instruments: works with --network host
#       GPIB-USB: works if linux-gpib is loaded on the host
#
# QUICK START (Linux host):
#   docker compose up          # see docker-compose.yml
#
# MANUAL RUN (Linux host):
#   docker build -t keithley-iv-suite:2.0.0 .
#   xhost +local:docker
#   docker run --rm -it \
#     -e DISPLAY=$DISPLAY \
#     -v /tmp/.X11-unix:/tmp/.X11-unix \
#     --device /dev/bus/usb \
#     --network host \
#     -v iv_data:/root/Documents/IV_Data \
#     keithley-iv-suite:2.0.0
#
# WINDOWS HOST (Ethernet VISA only):
#   See scripts/run_docker_windows.bat
#   For the native Windows EXE instead, see scripts/build_installer.bat
# ============================================================

FROM python:3.11-slim-bookworm

# ── System dependencies for PyQt6 / X11 / USB VISA ──────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # X11 / OpenGL
    libgl1-mesa-glx \
    libglib2.0-0 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libdbus-1-3 \
    # XCB platform plugin (required by Qt6)
    libxcb1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    # VISA / USB
    libusb-1.0-0 \
    usbutils \
    # pyserial / pyusb runtime support
    python3-serial \
    # Fonts
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# ── Python environment ───────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
COPY . .

# Output directory (mount a host volume to persist data)
RUN mkdir -p /root/Documents/IV_Data

# ── Runtime ──────────────────────────────────────────────────────────────────
ENV QT_QPA_PLATFORM=xcb
ENV PYTHONUNBUFFERED=1

VOLUME ["/root/Documents/IV_Data"]

CMD ["python", "main.py"]
