"""
Vision system for the Dog Trainer device.

Uses Picamera2 for camera access and Ultralytics YOLO for object detection
and classification.

Usage:
    vision = VisionSystem()
    frame = vision.get_frame()  # Get BGR frame
"""

from picamera2 import Picamera2
from ultralytics import YOLO
import cv2
import numpy as np
import time
import config


class VisionSystem:
    def __init__(self):
        print("[VISION] Loading detector...")
        self.detector = YOLO(config.DETECTOR_MODEL)

        print("[VISION] Loading classifier...")
        self.classifier = YOLO(config.CLASSIFIER_MODEL)

        # Init camera
        self.picam2 = Picamera2()
        # Configure camera preview size and format
        cfg = self.picam2.create_preview_configuration(
            main={"size": (config.FRAME_WIDTH, config.FRAME_HEIGHT), "format": "RGB888"}
        )
        self.picam2.configure(cfg)
        self.picam2.start()
        time.sleep(2) # allow camera to warm up

    def get_frame(self):
        """Returns BGR frame"""
        frame = self.picam2.capture_array() # RGB format
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # convert to BGR

    def detect_dog(self, frame):
        small = cv2.resize(frame, (320, 240)) # downscale for faster detection
        r = self.detector(small, verbose=False, device='cpu')[0] # use CPU, since this will be running on a raspberryPi

        dog_box = None

        if r.boxes is None:
            return None

        for box in r.boxes:
            cls_id = int(box.cls[0]) # class ID
            conf = float(box.conf[0]) # confidence
            if cls_id == 16 and conf > config.DET_CONF: 
                # Upscale bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0] * 2) # 320x240 -> 640x480
                dog_box = (x1, y1, x2, y2)
                break

        return dog_box

    # Extracts the dog crop from the frame given the bounding box, and run classification on it
    def classify_pose(self, crop):
        try:
            r = self.classifier(crop, device='cpu')[0] # use CPU, since this will be running on a raspberryPi
            if r.probs is None:
                return None, 0.0
            idx = r.probs.top1 # top-1 predicted class index
            conf = float(r.probs.top1conf) # confidence of top-1 prediction
            label = r.names[idx]
            return label, conf # pose label and confidence
        except:
            return None, 0.0

    def close(self):
        self.picam2.close() # release camera resources
