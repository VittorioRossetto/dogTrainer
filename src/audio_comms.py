import tempfile
import shutil
import subprocess
import os
import sys
import time


def _run(cmd, check=True, capture_output=False):
    try:
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
    except FileNotFoundError:
        return None


def _find_pulseaudio_sink(keyword):
    p = _run(["pactl", "list", "sinks"], check=False, capture_output=True)
    if p is None or p.returncode != 0:
        return None

    text = p.stdout
    name = None
    desc = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            name = line.split("Name:", 1)[1].strip()
            desc = None
        elif line.startswith("Description:"):
            desc = line.split("Description:", 1)[1].strip()
            if name and desc and keyword.lower() in desc.lower():
                return name
    return None


def _set_default_sink(sink_name):
    r = _run(["pactl", "set-default-sink", sink_name], check=False)
    return r is not None and r.returncode == 0


def _play_file(path):
    player = shutil.which("paplay") or shutil.which("ffplay") or shutil.which("aplay")
    if not player:
        print("No audio player found (paplay/ffplay/aplay). Install one and retry.")
        return False

    if player.endswith("ffplay"):
        cmd = [player, "-nodisp", "-autoexit", "-hide_banner", path]
    else:
        cmd = [player, path]

    p = _run(cmd, check=False)
    return p is not None and p.returncode == 0


def say(text, sink_keyword="VTIN K1", rate=140, voice=None):
    """Speak `text` through the Bluetooth speaker whose description contains
    `sink_keyword`. Generation uses `espeak` or `pico2wave` if available.

    Blocks until playback finishes. Returns True on success, False otherwise.
    """
    if not text:
        return False

    # Try to find and set the BT sink as default (best-effort)
    if shutil.which("pactl"):
        sink = _find_pulseaudio_sink(sink_keyword)
        if sink:
            _set_default_sink(sink)

    # Create temporary WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name

    try:
        # Prefer espeak
        if shutil.which("espeak"):
            cmd = ["espeak", "-w", wav_path, f"-s{int(rate)}"]
            if voice:
                cmd.extend(["-v", voice])
            cmd.append(text)
            r = _run(cmd, check=False)
            if r is None or r.returncode != 0:
                print("espeak failed to generate audio")
        elif shutil.which("pico2wave"):
            # pico2wave takes text in quotes
            cmd = ["pico2wave", "-w", wav_path, text]
            r = _run(cmd, check=False)
            if r is None or r.returncode != 0:
                print("pico2wave failed to generate audio")
        else:
            print("No TTS engine found (espeak/pico2wave). Install one and retry.")
            return False

        # Small delay to ensure file is written on slow FS
        time.sleep(0.05)

        ok = _play_file(wav_path)
        return ok
    finally:
        try:
            os.remove(wav_path)
        except Exception:
            pass
