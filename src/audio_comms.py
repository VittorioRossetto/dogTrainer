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


def play_recording(name_or_path, sink_keyword="VTIN K1"):
    """Play a prerecorded audio file.

    - If `name_or_path` is an absolute or relative path to an existing file, it will be played.
    - Otherwise we look for the file inside a `recordings/` directory next to this module.
      If `name_or_path` has no extension, `.wav` will be appended.

    Returns True on success, False otherwise.
    """
    if not name_or_path:
        return False

    # If provided path exists, use it directly
    if os.path.isabs(name_or_path) or os.path.exists(name_or_path):
        candidate = name_or_path
        if not os.path.exists(candidate):
            return False
        return _play_file(candidate)

    # Otherwise search recordings/ next to this file
    base_dir = os.path.dirname(__file__)
    recordings_dir = os.path.join(base_dir, "recordings")
    # Try as given, then with .wav
    candidates = [os.path.join(recordings_dir, name_or_path)]
    if not os.path.splitext(name_or_path)[1]:
        candidates.append(candidates[0] + ".wav")

    for c in candidates:
        if os.path.exists(c):
            return _play_file(c)

    return False


def play_bytes(data: bytes, suffix=".wav", sink_keyword="VTIN K1"):
    """Play raw audio bytes by writing to a temporary file and playing it.

    `data` should be raw audio content suitable for the chosen player (e.g. a WAV file's bytes).
    Returns True on success, False otherwise.
    """
    if not data:
        return False

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tmp_path = tf.name
        try:
            tf.write(data)
            tf.flush()
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return False

    try:
        time.sleep(0.02)
        return _play_file(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def play_base64(b64str: str, suffix=".wav", sink_keyword="VTIN K1"):
    """Decode a base64-encoded audio string and play it.

    Useful when receiving audio blobs over WebSocket/HTTP as base64.
    """
    if not b64str:
        return False
    try:
        import base64

        data = base64.b64decode(b64str)
    except Exception:
        return False
    return play_bytes(data, suffix=suffix, sink_keyword=sink_keyword)
