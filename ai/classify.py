from ultralytics import YOLO

class PoseClassifier:
    def __init__(self, model_path="../model/best.pt"):
        self.model = YOLO(model_path)

    def classify(self, frame):
        results = self.model(frame)
        pred = results[0].probs.top1
        label = results[0].names[pred]
        conf = results[0].probs.top1conf
        return label, conf