from gpiozero import AngularServo
import time
import config


class ServoController:
    def __init__(self):
        self.pin = config.SERVO_PIN
        # Match original pulse range ~600..2400 microseconds
        self.servo = AngularServo(
            self.pin,
            min_angle=-90,
            max_angle=90,
            min_pulse_width=0.0006,
            max_pulse_width=0.0024,
        )
        self.angle = None
        # Ensure servo always starts at 90 degrees
        self.set_angle(90)

    def set_angle(self, angle):
        """Only update servo if angle changes"""
        if self.angle == angle:
            return

        if angle is None:
            return

        # clamp to supported range
        if angle < -90:
            angle = -90
        elif angle > 90:
            angle = 90

        self.servo.angle = angle
        self.angle = angle

    def sweep(self):
        # Start at 90, move to 0, wait 0.5s, then move back to 90
        self.set_angle(90)
        time.sleep(0.1)
        self.set_angle(0)
        time.sleep(0.5)
        self.set_angle(90)
        time.sleep(0.1)

    def stop(self):
        # stop sending pulses but keep the servo object usable
        self.servo.value = None
