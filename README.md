# dogTrainer

Project for an automated dog trainer that performs dog pose recognition, speaks instructions, and dispenses treats via a servo. The system includes:

- A device application (Raspberry Pi / Linux) that runs a vision pipeline, servo control, and a WebSocket server for host/frontend control.
- A React frontend that connects via WebSocket to the device for manual control and sending recorded audio.
- An optional InfluxDB persistence pipeline (collector + writer) to store events and metrics for visualization.

**Dataset:**

Visit the training dataset used for pose classification:

https://universe.roboflow.com/vitto-rossetto-nbvy6/dog-pose-ntugs

---

**Quick Links**

- Device main: `src/main.py`
- Device host comms / WS server: `src/host_comms.py`
- Audio helpers (TTS + playback): `src/audio_comms.py`
- Influx writer: `src/influx_writer.py`
- Influx collector & API: `src/influx_collector.py`, `src/influx_api.py`
- Frontend app: `frontend/` (React + Vite)
- Scripts: `scripts/start_influx_services.py`

---

**Features**

- Real-time pose classification and pose transition events
- Device-hosted WebSocket server for low-latency bidirectional commands
- Commands from host/frontend: `set_mode`, `servo` actions, `treat_now`, `audio` (TTS or prerecorded/base64)
- Audio: TTS via `espeak` or `pico2wave`, plus playback of prerecorded files (`src/recordings/`) and base64 audio blobs
- Optional persistence to InfluxDB (supports v2 client, v1 client, or HTTP line-protocol fallback)
- Simple React UI for manual control and an Influx viewer

---

Requirements

- Python 3.8+ on the device and host machines
- System packages (device): `ffmpeg`/`pulseaudio` utilities for audio playback (e.g. `paplay`, `ffplay`, `aplay`), and TTS engines like `espeak` or `pico2wave` for TTS
- Python packages (recommended): `flask`, `websockets`, `requests`, `opencv-python`, `torch` (if using the included PyTorch models), plus `influxdb-client` or `influxdb` if you want Python client support
- Node.js and npm/yarn for building and running the frontend

Note: The project includes an HTTP fallback for Influx v1 (line-protocol POST) so the Python Influx libraries are optional for simple setups.

Models aren't provided by default, given the dimensions:
- `model`/`yolov8n.pt` will be installed automatically on first run
- `model`/`best.pt` has to be manually trained by running `notebook`/`dogPoseClassifierTrain.ipynb` either locally or on colab.

---

Device quickstart (Raspberry Pi)

1. Create and activate a virtual environment and install Python deps (example:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Ensure audio tools and TTS engines are installed (example on Debian/Ubuntu):

```bash
sudo apt update
sudo apt install pulseaudio-utils espeak ffmpeg
```

3. Start the device app (it runs a Flask status endpoint and a WebSocket server):

```bash
python3 src/main.py
```

4. Default device WebSocket server URL (used by the frontend):

```
ws://<DEVICE_IP>:8765/ws
```

Replace `<DEVICE_IP>` with your Pi's IP (e.g. `192.168.80.173`).

---

Influx collector & API (optional)

These components run on the Influx host (or same machine) and connect to the device WebSocket to receive events and write them into `dog_training` database.

1. Configure `src/influx_collector.py` to point at your device WS and Influx server.
2. Start the collector and API:

```bash
python3 scripts/start_influx_services.py
```

3. The collector writes events to Influx and the `src/influx_api.py` exposes a small HTTP proxy used by the frontend viewer.

Note: If your Influx version is v1.x (e.g. 1.6.7), the writer will use an HTTP line-protocol fallback when the Python client isn't available.

---

Frontend (development)

1. From the `frontend/` directory, install dependencies and run the dev server:

```bash
cd frontend
npm install
npm run dev
```

2. Open the UI in your browser and connect to the device WebSocket (use the Connect box). You can:
- Send TTS text and prerecorded audio
- Upload a small audio file (the UI will send base64 over WebSocket)
- Dispense treats and control servo actions

Frontend messages (examples sent to device over WS):

- Set mode: `{ "cmd": "set_mode", "mode": "auto" }`
- Treat now: `{ "cmd": "treat_now" }`
- Servo sweep: `{ "cmd": "servo", "action": "sweep" }`
- TTS: `{ "cmd": "audio", "text": "Good dog!" }`
- Send recorded audio (base64): `{ "cmd": "audio", "b64": "<BASE64>", "filename": "cheer.wav" }`

The device responds by broadcasting event envelopes to connected UIs. Events look like:

```json
{ "type": "event", "event": "pose_transition", "timestamp": 1234567890.0, "payload": { ... } }
```

---

Developer notes

- `src/host_comms.py` hosts the WebSocket server and interfaces between the device and UI/host. Register a command handler with `register_command_handler(fn)`.
- `src/audio_comms.py` provides `say(text)`, `play_recording(name_or_path)`, and `play_base64(b64)` for audio playback.
- For large audio transfers prefer an HTTP upload endpoint and play from disk rather than sending very large base64 blobs over WS.

---

Author

Vittorio Rossetto
- [Github](https://github.com/VittorioRossetto)
- [Linkedin](https://www.linkedin.com/in/vittorio-rossetto-508086333/)
---

Contributing

Contributions welcome. Open an issue or PR describing your change. Suggested next improvements:

---

License
  