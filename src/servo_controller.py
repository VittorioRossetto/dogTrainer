"""
Servo controller using PCA9685 via Adafruit ServoKit.

This module initializes a servo controller and provides methods to set the
servo angle, perform a sweep motion, and stop the servo.

Usage:
    from servo_controller import ServoController
    servo = ServoController()
    servo.set_angle(45)  # Set servo to 45 degrees
    servo.sweep()        # Perform a sweep motion
    servo.stop()        # Stop the servo
"""


# Import necessary libraries
from adafruit_servokit import ServoKit
import time
import config

class ServoController:
    def __init__(self):
        # Initialize PCA9685 with 16 channels
        self.kit = ServoKit(channels=16)

        # Servo connected to config.SERVO_PIN
        self.channel = config.SERVO_PIN

        # ServoKit uses 0–180° range by default
        self.angle = None

        # Start at 90 degrees
        self.set_angle(90)

    def set_angle(self, angle):
        if angle is None or angle == self.angle:
            return

        # clamp -90..90
        angle = max(-90, min(90, angle))

        # Convert -90..90 into 0..180 for ServoKit
        self.kit.servo[self.channel].angle = angle + 90
        self.angle = angle

    # Perform a sweep motion: 90 -> 0 -> 90
    def sweep(self):
        self.set_angle(90)
        time.sleep(0.1)
        self.set_angle(0)
        time.sleep(0.5)
        self.set_angle(90)
        time.sleep(0.1)

    def stop(self):
        # Turn off the PWM pulse (servo relaxes)
        self.kit.servo[self.channel].angle = None