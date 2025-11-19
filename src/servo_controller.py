import pigpio
import time
import config


class ServoController:
    def __init__(self):
        self.pi = pigpio.pi()
        self.pin = config.SERVO_PIN
        self.angle = None

    def set_angle(self, angle):
        """Only update servo if angle changes"""
        if self.angle == angle:
            return

        pulse = 1500 + (angle * 10)   # ~1500μs center, ±900μs span
        self.pi.set_servo_pulsewidth(self.pin, pulse)
        self.angle = angle

    def sweep(self):
        self.set_angle(0)
        time.sleep(0.3)
        self.set_angle(90)
        time.sleep(1.0)
        self.set_angle(0)
        time.sleep(0.3)

    def stop(self):
        self.pi.set_servo_pulsewidth(self.pin, 0)
