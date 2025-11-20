#!/usr/bin/env python3
"""Collector: subscribe to device WebSocket and write events to local InfluxDB.

This script runs on the machine where InfluxDB is hosted (e.g. your laptop)
and connects to the device WebSocket server (the Raspberry Pi) to receive
events and persist them locally into the `dog_training` database/bucket.

Example:
  pip install websockets influxdb
  python3 scripts/influx_collector.py --ws ws://192.168.80.173:8765/ws

Configuration:
  - The script uses the project's `src/config.py` INFLUX_* settings. Edit
    `src/config.py` to point `INFLUX_URL` and `INFLUX_DB` appropriately.
"""
import asyncio
import json
import time
import argparse
import sys


async def _collector_loop(ws_url: str, reconnect_interval: float):
    import websockets
    from influx_writer import write_event

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
                        print("[COLLECTOR] Received non-JSON message, ignoring:", msg)
                        continue

                    # If message looks like an event envelope, write it. Otherwise
                    # wrap it as a status event.
                    if isinstance(data, dict) and data.get("type") == "event":
                        ok = write_event(data)
                        print(f"[COLLECTOR] Wrote event {data.get('event')} -> {ok}")
                    else:
                        envelope = {
                            "type": "event",
                            "event": "status",
                            "timestamp": time.time(),
                            "payload": data,
                        }
                        ok = write_event(envelope)
                        print(f"[COLLECTOR] Wrote status -> {ok}")

        except Exception as e:
            print("[COLLECTOR] Connection error:", e)
        print(f"[COLLECTOR] Reconnecting in {reconnect_interval}s...")
        await asyncio.sleep(reconnect_interval)


def main(argv=None):
    p = argparse.ArgumentParser(description="WebSocket -> Influx collector")
    p.add_argument("--ws", default="ws://192.168.80.173:8765/ws", help="WebSocket URL of device WS server")
    p.add_argument("--reconnect", type=float, default=5.0, help="Reconnect interval (s)")
    args = p.parse_args(argv)

    try:
        asyncio.run(_collector_loop(args.ws, args.reconnect))
    except KeyboardInterrupt:
        print("[COLLECTOR] Exiting")
        return 0


if __name__ == "__main__":
    sys.exit(main())
