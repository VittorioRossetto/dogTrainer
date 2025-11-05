from ultralytics import YOLO

class DogDetector:
    def __init__(self, model_path="yolov8n.pt"):
        self.model = YOLO(model_path)

    def detect(self, frame):
        results = self.model(frame)
        for box in results[0].boxes:
            if int(box.cls) == 16:
                return True
        return False