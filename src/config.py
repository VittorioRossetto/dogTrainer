# MODE (auto/manual) is stored here so all modules can read it
MODE = "auto"     # "auto" or "manual"

# Vision
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DETECTOR_MODEL = "../model/yolov8n.pt"
CLASSIFIER_MODEL = "../model/best.pt"
DET_CONF = 0.30
POSE_CONF = 0.50

# Behavior logic timers
TREAT_WINDOW = 5        # seconds
TREAT_COOLDOWN = 5*60   # 5 minutes cooldown after treat

# Host communication: set to the host endpoint to receive status updates from
# this device, e.g. "http://192.168.1.10:3000/api/status". Set to `None`
# to disable sending to a remote host.
HOST_URL = None
# WebSocket host URL (preferred for low-latency bidirectional comms).
# Example: "ws://192.168.1.100:3000/ws"
HOST_WS_URL = None

# WebSocket reconnect interval (seconds)
WS_RECONNECT_INTERVAL = 5
# If the device should host a WebSocket server for UIs to connect directly,
# configure the port/path here. The server binds to 0.0.0.0 so the Pi is reachable
# on the network.
WS_SERVER_PORT = 8765
WS_SERVER_PATH = "/ws"

# Servo
SERVO_PIN = 18
MIN_PW = 0.0010
MAX_PW = 0.0020
TREAT_ANGLE = 60
REST_ANGLE = 0
