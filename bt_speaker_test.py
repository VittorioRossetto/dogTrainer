#!/usr/bin/env python3
"""
bt_speaker_test.py

Finds a PulseAudio sink whose description matches a keyword (default "VTIN K1"),
sets it as the default sink, moves existing sink inputs there, and plays a short
sine test tone.

Usage:
  python3 bt_speaker_test.py            # uses "VTIN K1"
  python3 bt_speaker_test.py --sink "VTIN K1"

Notes:
- Requires `pactl` (PulseAudio) or `pw-cli`/PipeWire compatibility providing `pactl`.
- Uses `paplay`, `ffplay`, or `aplay` (in that order) to play the generated WAV.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import wave
from math import sin, pi

SAMPLE_RATE = 44100

def run(cmd, check=True, capture_output=False):
    try:
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
    except FileNotFoundError:
        return None


def find_pulseaudio_sink(keyword):
    """Return sink name (e.g. alsa_output.blah) whose Description contains keyword."""
    p = run(["pactl", "list", "sinks"], check=False, capture_output=True)
    if p is None or p.returncode != 0:
        return None

    text = p.stdout
    lines = text.splitlines()
    name = None
    desc = None
    for line in lines:
        line = line.strip()
        if line.startswith("Name:"):
            name = line.split("Name:", 1)[1].strip()
            desc = None
        elif line.startswith("Description:"):
            desc = line.split("Description:", 1)[1].strip()
            if name and desc and keyword.lower() in desc.lower():
                return name
    return None


def set_default_sink(sink_name):
    r = run(["pactl", "set-default-sink", sink_name], check=False)
    return r is not None and r.returncode == 0


def move_existing_inputs(sink_name):
    p = run(["pactl", "list", "short", "sink-inputs"], check=False, capture_output=True)
    if p is None or p.returncode != 0:
        return False
    for line in p.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        input_id = parts[0]
        run(["pactl", "move-sink-input", input_id, sink_name], check=False)
    return True


def generate_tone_wav(path, freq=440.0, duration=1.0, amplitude=0.5):
    n_samples = int(SAMPLE_RATE * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            sample = amplitude * sin(2 * pi * freq * t)
            # 16-bit PCM
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            wf.writeframesraw(val.to_bytes(2, byteorder="little", signed=True))
        wf.writeframes(b"")


def play_file(path):
    # prefer paplay (PulseAudio), fall back to ffplay or aplay
    player = shutil.which("paplay") or shutil.which("ffplay") or shutil.which("aplay")
    if not player:
        print("No audio player found (paplay/ffplay/aplay). Install one and retry.")
        return False

    if player.endswith("ffplay"):
        # ffplay: suppress output, autoexit
        cmd = [player, "-nodisp", "-autoexit", "-hide_banner", path]
    else:
        cmd = [player, path]

    print("Playing test tone with:", " ".join(cmd))
    p = run(cmd, check=False)
    return p is not None and p.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Test Bluetooth speaker by name and play a tone.")
    parser.add_argument("--sink", default="VTIN K1", help="Sink description keyword to search for")
    parser.add_argument("--freq", type=float, default=440.0, help="Tone frequency in Hz")
    parser.add_argument("--duration", type=float, default=1.0, help="Tone duration in seconds")
    args = parser.parse_args()

    if shutil.which("pactl") is None:
        print("pactl not found. This script requires PulseAudio utilities (pactl).")
        sys.exit(1)

    print(f"Searching for sink matching: {args.sink}")
    sink = find_pulseaudio_sink(args.sink)
    if not sink:
        print("Sink not found. Is the speaker connected and powered on?")
        sys.exit(2)

    print(f"Found sink: {sink}")
    if set_default_sink(sink):
        print(f"Set {sink} as default sink.")
    else:
        print("Failed to set default sink (permission or pactl error). Continuing to play to default.")

    moved = move_existing_inputs(sink)
    if moved:
        print("Moved existing audio streams to the sink (if any).")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name
    try:
        print(f"Generating {args.duration}s {args.freq}Hz tone at {wav_path}")
        generate_tone_wav(wav_path, freq=args.freq, duration=args.duration)
        ok = play_file(wav_path)
        if ok:
            print("Playback finished successfully.")
            sys.exit(0)
        else:
            print("Playback failed.")
            sys.exit(3)
    finally:
        try:
            import os
            os.remove(wav_path)
        except Exception:
            pass

if __name__ == '__main__':
    main()
