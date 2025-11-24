import cv2
from ultralytics import YOLO
import numpy as np

# -------------------------------
# CONFIG
# -------------------------------
CLASSIFIER_MODEL = "model/best.pt"   # or "best.onnx"
USE_ONNX = CLASSIFIER_MODEL.endswith(".onnx")
DETECTOR_MODEL = "model/yolov8n.pt"  # auto-download
CONF_THRESH = 0.3
POSE_CONF_THRESH = 0.5

# -------------------------------
# LOAD MODELS
# -------------------------------
print("[INFO] Loading detector...")
detector = YOLO(DETECTOR_MODEL)

print("[INFO] Loading classifier...")
classifier = YOLO(CLASSIFIER_MODEL)


# -------------------------------
# VIDEO STREAM
# -------------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Cannot open webcam")


def classify_pose(frame):
    """Run classification model and return label + confidence"""
    results = classifier(frame, device='cpu')
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
        print("[WARN] Frame grab failed")
        break

    # -------------------------------
    # RUN DOG DETECTOR
    # -------------------------------
    det_results = detector(frame, verbose=False, device='cpu')[0]
    
    dog_found = False

    if det_results.boxes is not None:
        for box in det_results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])

            # "dog" class in COCO dataset = 16
            if cls_id == 16 and conf > CONF_THRESH:
                dog_found = True
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # draw bbox
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)

                # -------------------------------
                # CROP DOG AND CLASSIFY POSE
                # -------------------------------
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    label, pose_conf = classify_pose(crop)

                    if label and pose_conf > POSE_CONF_THRESH:
                        text = f"{label} ({pose_conf:.2f})"
                    else:
                        text = "Uncertain"
                else:
                    text = "Detection Error"

                cv2.putText(frame, text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,0), 2)

    if not dog_found:
        cv2.putText(frame, "NO DOG", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)

    # -------------------------------
    # SHOW FRAME
    # -------------------------------
    cv2.imshow("Dog Detector + Pose Classifier", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


cap.release()
cv2.destroyAllWindows()
