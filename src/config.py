# MODE (auto/manual) is stored here so all modules can read it
MODE = "auto"     # "auto" or "manual"

# Vision
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DETECTOR_MODEL = "../model/yolov8n.pt"
CLASSIFIER_MODEL = "../model/best.pt"
DET_CONF = 0.50 # confidence threshold for dog detection
POSE_CONF = 0.70 # confidence threshold for pose classification

# Behavior logic timers
TREAT_WINDOW = 10       # seconds
TREAT_COOLDOWN = 5*60   # 5 minutes cooldown after treat

# Host communication: set to the host endpoint to receive status updates from
HOST_URL = None
# WebSocket host URL (preferred for low-latency bidirectional comms).
# Example: "ws://192.168.1.100:3000/ws"
HOST_WS_URL = None

# WebSocket reconnect interval (seconds)
WS_RECONNECT_INTERVAL = 5
# WebSocket server settings (for incoming connections from host UIs)
WS_SERVER_PORT = 8765
WS_SERVER_PATH = "/ws"

# InfluxDB settings: prefer InfluxDB v2 (token/org/bucket). If TOKEN is empty
# the writer will attempt an InfluxDB v1 client using INFLUX_DB.
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = ""  # set for InfluxDB v2
INFLUX_ORG = ""
INFLUX_BUCKET = "dog_training"
INFLUX_DB = "dog_training"  # for InfluxDB v1 compatibility

# Servo
SERVO_PIN = 18 
MIN_PW = 0.0010  
MAX_PW = 0.0020
TREAT_ANGLE = 0 
REST_ANGLE = 90
