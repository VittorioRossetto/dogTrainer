"""
Main application logic for the Dog Trainer device.
Handles vision processing, servo control, and host communications.

Uses OpenCV for video capture and processing, a custom VisionSystem for
dog detection and pose classification, and a ServoController for treat dispensing.

The application supports two modes:
- Automatic mode: detects dog poses and dispenses treats based on predefined logic.
- Manual mode: responds to commands from the host UI for treat dispensing and audio playback.

Usage:
  python3 src/main.py
"""

# Import necessary modules
import time
import cv2
import config
from vision import VisionSystem
from servo_controller import ServoController
from audio_comms import say, play_base64, play_recording
import host_comms
import os
import glob

# Automatic mode logic
def automatic_mode_logic(mode_state, servo, label):
    now = time.time()

    # STATE 1 — Dog standing -> instruct to sit
    if mode_state["stage"] == "waiting_stand":
        # Check the current pose
        if label == "stand":
            say("sit") # Instruct the dog
            mode_state["last_command_time"] = now # record command time
            mode_state["stage"] = "waiting_sit" # move to next state

    # STATE 2 — Dog must sit within TREAT_WINDOW (find in config.py) seconds
    elif mode_state["stage"] == "waiting_sit":
        if now - mode_state["last_command_time"] > config.TREAT_WINDOW:
            # timeout -> restart
            mode_state["stage"] = "waiting_stand"
        # Check for overrides
        if mode_state.get("treat_disabled"):
            return

        # Check the current pose for sitting, give treat if so, since the dog followed command
        if label == "sit":
            servo.sweep() # dispense treat
            say("Good dog!") # praise the dog
            mode_state["stage"] = "cooldown" # move to cooldown
            mode_state["cooldown_until"] = now + config.TREAT_COOLDOWN
            host_comms.send_event("treat_given", {"reason": "auto"})
            host_comms.send_event("servo_action", {"action": "sweep"})

    # STATE 3 — Cooldown 5 minutes
    elif mode_state["stage"] == "cooldown":
        # Wait for cooldown period to expire
        if now > mode_state["cooldown_until"]:
            mode_state["stage"] = "waiting_stand" # restart cycle after cooldown


def main():
    host_comms.start_server() # start WebSocket server for host communications

    vision = VisionSystem() # initialize vision system
    servo = ServoController() # initialize servo controller

    # Initialize mode state for automatic mode logic
    mode_state = {
        "stage": "waiting_stand",
        "last_command_time": 0,
        "cooldown_until": 0
    }

    try:
        # Register host command handler
        def _on_host_command(msg):
            # Expected messages: {"cmd": "set_mode", ...} or {"cmd": "servo", ...}
            cmd = msg.get("cmd") # command type
            # Validate command
            if not cmd:
                print("[HOST CMD] Invalid command (no 'cmd'):", msg) # log error
                return

            # Handle different command types
            # Set mode command (auto/manual)
            if cmd == "set_mode":
                m = msg.get("mode")
                if m in ["auto", "manual"]:
                    config.MODE = m # update mode
                    print(f"[HOST] Mode switched to: {config.MODE}")
                    host_comms.send_event("mode_changed", {"mode": config.MODE})
                else:
                    print("[HOST CMD] Invalid mode:", m) # log error

            elif cmd == "servo": 
                action = msg.get("action")
                if action == "sweep":
                    servo.sweep() # dispense treat
                    host_comms.send_event("servo_action", {"action": "sweep"}) # notify host
                    host_comms.send_event("treat_given", {"reason": "host_command"}) # notify host
                else:
                    print("[HOST CMD] Unknown servo action:", action)

            elif cmd == "audio":
                # Support three modes:
                # - raw text -> TTS via say()
                # - b64 -> base64-encoded audio data to play
                # - filename/file -> play a prerecorded file from recordings/ or path
                text = msg.get("text") # raw text for TTS
                b64 = msg.get("b64") # base64-encoded audio data
                filename = msg.get("filename") or msg.get("file") # filename or file path

                try:
                    if b64:
                        ok = play_base64(b64) # play base64 audio
                        host_comms.send_event("audio_playback", {"method": "b64", "filename": filename if filename else None, "ok": bool(ok)}) # notify host
                    elif filename:
                        ok = play_recording(filename) # play prerecorded file
                        host_comms.send_event("audio_playback", {"method": "file", "filename": filename, "ok": bool(ok)}) # notify host
                    elif text:
                        name = text.strip()
                        # only treat plain basenames (no path separators) as recording names
                        if name and os.path.basename(name) == name:
                            candidate_dirs = [
                                os.path.join(os.getcwd(), "recordings"), # current working dir recordings/
                                os.path.join(os.path.dirname(__file__), "recordings"), # src/recordings/ dir in case we are running from parent
                                "recordings",
                            ]
                            allowed_exts = {".wav", ".mp3", ".ogg", ".m4a", ".flac"}
                            found_file = None

                            # Search for the recording in candidate dirs (recordings/)
                            for d in candidate_dirs:
                                d = os.path.abspath(d) 
                                if not os.path.isdir(d):
                                    continue
                                for p in glob.glob(os.path.join(d, name + ".*")):
                                    if os.path.splitext(p)[1].lower() in allowed_exts:
                                        found_file = p # found the file
                                        break
                                if found_file:
                                    break

                            if found_file:
                                ok = play_recording(found_file)
                                host_comms.send_event("audio_playback", {"method": "file", "filename": os.path.basename(found_file), "ok": bool(ok)})
                                host_comms.send_event("audio_playback", {"method": "tts", "text": text}) # also log the original text
                                return
                        say(text) # TTS playback
                        host_comms.send_event("audio_playback", {"method": "tts", "text": text}) 
                    else:
                        print("[HOST CMD] audio command missing payload (text/b64/file):", msg) # log error
                except Exception as e:
                    print("[HOST CMD] audio playback error:", e)
                    host_comms.send_event("audio_playback", {"method": "error", "error": str(e)})

            elif cmd == "collector_broadcast":
                # Collector can ask the device to rebroadcast an event to all
                # connected UIs. Expected shape: {cmd:'collector_broadcast', event: '<name>', payload: {...}}
                ev = msg.get('event')
                payload = msg.get('payload', {}) or {}
                if ev:
                    host_comms.send_event(ev, payload)
                else:
                    print('[HOST CMD] collector_broadcast missing event field')

            # Treat override commands
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
                else:
                    print("[HOST CMD] Unknown override_treat mode:", mode)

            # Immediate treat command
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
