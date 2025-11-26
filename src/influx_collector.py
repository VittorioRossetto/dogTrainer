"""Collector: subscribe to device WebSocket and write events to local InfluxDB.

This script runs on the machine where InfluxDB is hosted (e.g. your laptop)
and connects to the device WebSocket server (the Raspberry Pi) to receive
events and persist them locally into the `dog_training` database/bucket.

Example:
  pip install websockets influxdb
  python3 scripts/influx_collector.py --ws ws://raspberrypi.local:8765/ws

Configuration:
  - The script uses the project's `src/config.py` INFLUX_* settings. Edit
    `src/config.py` to point `INFLUX_URL` and `INFLUX_DB` appropriately.
"""
import asyncio
import json
import time
import argparse
import sys
from collections import deque
from datetime import datetime


async def _collector_loop(ws_url: str, reconnect_interval: float):
    import websockets
    from influx_writer import write_event

    # keep a short history of recent audio_playback events to match
    # subsequent pose_transition events (for detecting command success)
    recent_audio = deque(maxlen=200)  # entries: dict(ts, text, filename, matched)

    daily_counters = {}

    def _today_key(ts=None):
        return datetime.utcfromtimestamp(ts or time.time()).strftime('%Y-%m-%d')

    def _inc_counter(kind: str, ts=None, delta: int = 1):
        k = _today_key(ts)
        if k not in daily_counters:
            daily_counters[k] = {'treat': 0, 'success': 0}
        daily_counters[k][kind] += delta
        # write a summary event so it's queryable in Influx
        envelope = {
            'type': 'event',
            'event': 'daily_counters',
            'timestamp': time.time(),
            'payload': {
                'date': k,
                'treat_count': daily_counters[k]['treat'],
                'command_success_count': daily_counters[k]['success'],
            }
        }
        try:
            write_event(envelope)
        except Exception:
            print('[COLLECTOR] Failed to write daily_counters')

    while True:
        try:
            print(f"[COLLECTOR] Connecting to {ws_url}")
            async with websockets.connect(ws_url) as ws:
                print("[COLLECTOR] Connected")
                async for msg in ws:
                    # Expect JSON event envelopes from device
                    try:
                        data = json.loads(msg)
                    except Exception:
                        print('[COLLECTOR] Received non-JSON message, ignoring:', msg)
                        continue

                    # If message looks like an event envelope, write it. Otherwise
                    # wrap it as a status event.
                    if isinstance(data, dict) and data.get('type') == 'event':
                        ev = data.get('event')
                        payload = data.get('payload', {}) or {}
                        ts = data.get('timestamp') or time.time()

                        # Track audio_playback events for later matching
                        if ev == 'audio_playback':
                            # payload may contain 'text' or 'filename' depending on origin
                            entry = {
                                'ts': ts,
                                'text': payload.get('text') or '',
                                'filename': payload.get('filename') or payload.get('file') or '',
                                'matched': False,
                            }
                            recent_audio.append(entry)

                        # When a pose_transition arrives, try to match a recent audio
                        # playback that requested that pose within a 5s window.
                        if ev == 'pose_transition':
                            to_pose = payload.get('to')
                            pose_ts = ts
                            matched_any = False
                            if to_pose:
                                to_lower = str(to_pose).lower()
                                # scan recent_audio from newest to oldest to prefer recent audio
                                for a in list(recent_audio)[::-1]:
                                    if a.get('matched'):
                                        continue
                                    a_ts = a.get('ts', 0)
                                    if a_ts > pose_ts:
                                        # audio after pose -> ignore
                                        continue
                                    if pose_ts - a_ts > 5.0:
                                        # too old
                                        continue
                                    # match if the audio text or filename contains the target pose
                                    text = (a.get('text') or '').lower()
                                    fname = (a.get('filename') or '').lower()
                                    if to_lower in text or to_lower in fname:
                                        # success!
                                        a['matched'] = True
                                        matched_any = True
                                        # emit a command_success event
                                        success_env = {
                                            'type': 'event',
                                            'event': 'command_success',
                                            'timestamp': pose_ts,
                                            'payload': {
                                                'command_text': a.get('text'),
                                                'filename': a.get('filename'),
                                                'target_pose': to_pose,
                                                'audio_ts': a_ts,
                                                'pose_ts': pose_ts,
                                            }
                                        }
                                        try:
                                            ok = write_event(success_env)
                                            print(f"[COLLECTOR] Wrote command_success -> {ok}")
                                        except Exception:
                                            print('[COLLECTOR] Failed to write command_success')
                                        # increment per-day counter
                                        _inc_counter('success', ts=pose_ts, delta=1)
                                        # send an acknowledgement back to the device so it can
                                        # broadcast the success to connected UIs
                                        try:
                                            await ws.send(json.dumps({
                                                'cmd': 'collector_broadcast',
                                                'event': 'command_success',
                                                'payload': success_env.get('payload', {})
                                            }))
                                            print('[COLLECTOR] Sent ack to device to broadcast command_success')
                                        except Exception as e:
                                            print('[COLLECTOR] Failed to send ack to device:', e)
                                        break

                            # continue to write the pose_transition as usual below

                        # If treat_given, increment treat counter
                        if ev == 'treat_given':
                            _inc_counter('treat', ts=ts, delta=1)

                        # write the original event to Influx
                        ok = write_event(data)
                        print(f"[COLLECTOR] Wrote event {ev} -> {ok}")

                    else:
                        envelope = {
                            'type': 'event',
                            'event': 'status',
                            'timestamp': time.time(),
                            'payload': data,
                        }
                        ok = write_event(envelope)
                        print(f"[COLLECTOR] Wrote status -> {ok}")

        except Exception as e:
            print("[COLLECTOR] Connection error:", e)
        print(f"[COLLECTOR] Reconnecting in {reconnect_interval}s...")
        await asyncio.sleep(reconnect_interval)


def main(argv=None):
    p = argparse.ArgumentParser(description="WebSocket -> Influx collector")
    p.add_argument("--ws", default="ws://raspberrypi.local:8765/ws", help="WebSocket URL of device WS server")
    p.add_argument("--reconnect", type=float, default=5.0, help="Reconnect interval (s)")
    args = p.parse_args(argv)

    try:
        asyncio.run(_collector_loop(args.ws, args.reconnect))
    except KeyboardInterrupt:
        print("[COLLECTOR] Exiting")
        return 0


if __name__ == "__main__":
    sys.exit(main())
