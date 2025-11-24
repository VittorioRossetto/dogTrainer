import cv2
from ultralytics import YOLO

# -----------------------------------
# CONFIG
# -----------------------------------
CLASSIFIER_MODEL = "model/best.pt"    # or best.onnx
POSE_CONF_THRESH = 0.5          # minimum confidence

# -----------------------------------
# LOAD MODEL
# -----------------------------------
print("[INFO] Loading classifier...")
model = YOLO(CLASSIFIER_MODEL)

# -----------------------------------
# VIDEO
# -----------------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Cannot access webcam")

def classify_pose(frame):
    # force CPU to prevent GPU errors
    results = model(frame, device="cpu")

    probs = results[0].probs
    if probs is None:
        return None, 0.0

    label_idx = probs.top1
    conf = float(probs.top1conf)
    label = results[0].names[label_idx]
    return label, conf


while True:
    ret, frame = cap.read()
    if not ret:
        break

    # classify whole frame
    label, conf = classify_pose(frame)

    if label and conf > POSE_CONF_THRESH:
        text = f"{label} ({conf:.2f})"
    else:
        text = "Uncertain"

    cv2.putText(frame, text, (20,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2)

    cv2.imshow("Pose Classifier Only", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
