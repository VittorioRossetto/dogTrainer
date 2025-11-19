import time
import cv2
import config
from vision import VisionSystem
from servo_controller import ServoController
from audio_comms import say
import host_comms


def automatic_mode_logic(mode_state, servo, label):
    now = time.time()

    # STATE 1 — Dog standing → instruct to sit
    if mode_state["stage"] == "waiting_stand":
        if label == "stand":
            say("Sit")
            mode_state["last_command_time"] = now
            mode_state["stage"] = "waiting_sit"

    # STATE 2 — Dog must sit within 5 seconds
    elif mode_state["stage"] == "waiting_sit":
        if now - mode_state["last_command_time"] > config.TREAT_WINDOW:
            # timeout → restart
            mode_state["stage"] = "waiting_stand"
        # Check for overrides
        if mode_state.get("treat_disabled"):
            return

        # Force treat if requested by host
        if mode_state.get("force_treat"):
            servo.sweep()
            say("Good dog!")
            mode_state["force_treat"] = False
            mode_state["stage"] = "cooldown"
            mode_state["cooldown_until"] = now + config.TREAT_COOLDOWN
            # send treat event through host_comms
            host_comms.send_event("treat_given", {"reason": "force_treat"})
            host_comms.send_event("servo_action", {"action": "sweep"})
            return

        if label == "sit":
            servo.sweep()
            say("Good dog!")
            mode_state["stage"] = "cooldown"
            mode_state["cooldown_until"] = now + config.TREAT_COOLDOWN
            host_comms.send_event("treat_given", {"reason": "auto"})
            host_comms.send_event("servo_action", {"action": "sweep"})

    # STATE 3 — Cooldown 5 minutes
    elif mode_state["stage"] == "cooldown":
        if now > mode_state["cooldown_until"]:
            mode_state["stage"] = "waiting_stand"


def main():
    host_comms.start_server()

    vision = VisionSystem()
    servo = ServoController()

    mode_state = {
        "stage": "waiting_stand",
        "last_command_time": 0,
        "cooldown_until": 0
    }

    try:
        # Register host command handler
        def _on_host_command(msg):
            # Expected messages: {"cmd": "set_mode", ...} or {"cmd": "servo", ...}
            cmd = msg.get("cmd")
            if not cmd:
                print("[HOST CMD] Invalid command (no 'cmd'):", msg)
                return

            if cmd == "set_mode":
                m = msg.get("mode")
                if m in ["auto", "manual"]:
                    config.MODE = m
                    print(f"[HOST] Mode switched to: {config.MODE}")
                    host_comms.send_event("mode_changed", {"mode": config.MODE})
                else:
                    print("[HOST CMD] Invalid mode:", m)

            elif cmd == "servo":
                action = msg.get("action")
                if action == "set_angle":
                    angle = msg.get("angle")
                    try:
                        servo.set_angle(int(angle))
                        host_comms.send_event("servo_action", {"action": "set_angle", "angle": angle})
                    except Exception as e:
                        print("[HOST CMD] servo set_angle error:", e)
                elif action == "sweep":
                    servo.sweep()
                    host_comms.send_event("servo_action", {"action": "sweep"})
                    host_comms.send_event("treat_given", {"reason": "host_command"})
                else:
                    print("[HOST CMD] Unknown servo action:", action)

            elif cmd == "audio":
                text = msg.get("text")
                if text:
                    say(text)
                    host_comms.send_event("audio_playback", {"text": text})

            elif cmd == "override_treat":
                mode = msg.get("mode")
                if mode == "disable":
                    mode_state["treat_disabled"] = True
                    print("[HOST] Treat logic disabled")
                    host_comms.send_event("treat_override", {"mode": "disable"})
                elif mode == "enable":
                    mode_state["treat_disabled"] = False
                    print("[HOST] Treat logic enabled")
                    host_comms.send_event("treat_override", {"mode": "enable"})
                elif mode == "force":
                    mode_state["force_treat"] = True
                    print("[HOST] Force treat requested")
                    host_comms.send_event("treat_override", {"mode": "force"})
                else:
                    print("[HOST CMD] Unknown override_treat mode:", mode)

            elif cmd == "treat_now":
                servo.sweep()
                say("Good dog!")
                host_comms.send_event("treat_given", {"reason": "treat_now"})
                host_comms.send_event("servo_action", {"action": "sweep"})

            else:
                print("[HOST CMD] Unknown command:", cmd)

        host_comms.register_command_handler(_on_host_command)

        previous_label = None

        while True:
            frame = vision.get_frame()
            dog_box = vision.detect_dog(frame)

            mode = config.MODE

            if dog_box:
                x1, y1, x2, y2 = dog_box
                crop = frame[y1:y2, x1:x2]
                label, conf = vision.classify_pose(crop)

                if label:
                    print(f"[POSE] {label} ({conf:.2f})")

                # detect pose transitions
                if 'previous_label' in locals():
                    prev = previous_label
                else:
                    prev = None
                if label != prev:
                    host_comms.send_event("pose_transition", {"from": prev, "to": label, "confidence": conf})
                previous_label = label

                # Automatic logic only when enabled
                if mode == "auto":
                    automatic_mode_logic(mode_state, servo, label)

                # Send state to host
                host_comms.send_status({
                    "mode": mode,
                    "dog_detected": True,
                    "pose": label,
                    "pose_confidence": conf,
                    "stage": mode_state["stage"],
                    "timestamp": time.time()
                })

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
                cv2.putText(frame, label, (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)

            else:
                cv2.putText(frame, "NO DOG", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255), 2)

            # cv2.imshow("Dog Trainer", frame) # Uncomment to see video feed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        servo.stop()
        vision.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
