"""WebSocket mediator: forwards messages between device(s) and UI(s).

Usage:
  pip install aiohttp
  python3 src/ws_mediator.py

Protocol (over WS):
  - On connect, clients should send a registration message:
      {"type": "register", "role": "device"}
      or
      {"type": "register", "role": "ui", "name": "frontend"}

  - UI -> device: send any JSON containing a `cmd` field. Server will forward
    that JSON to the registered device (if connected).

  - Device -> UI: send any JSON messages (events). Server will broadcast those
    to all connected UIs.

HTTP endpoints:
  - POST /api/status  -> accepts JSON and broadcasts to UIs (fallback from device)
  - GET  /api/clients -> returns connected clients (device + ui count)
"""
import asyncio
import json
from aiohttp import web, WSMsgType

DEVICE = None  # websocket for device (assume single device)
UIS = set()    # set of websocket objects for UIs


async def ws_handler(request):
    global DEVICE, UIS
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    role = None
    name = None
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                text = msg.data.strip()
                try:
                    data = json.loads(text)
                except Exception:
                    # pass through non-json text to UIs/device depending on role
                    if role == "device":
                        # broadcast raw text to UIs
                        await _broadcast_ui({"type": "raw", "text": text})
                    elif role == "ui":
                        # send raw text to device
                        if DEVICE:
                            await DEVICE.send_str(text)
                    continue

                # handle registration
                if isinstance(data, dict) and data.get("type") == "register":
                    r = data.get("role")
                    if r == "device":
                        DEVICE = ws
                        role = "device"
                        name = data.get("name")
                        await ws.send_json({"ok": True, "role": "device"})
                        print("[MEDIATOR] Device registered")
                        continue
                    elif r == "ui":
                        UIS.add(ws)
                        role = "ui"
                        name = data.get("name")
                        await ws.send_json({"ok": True, "role": "ui"})
                        print(f"[MEDIATOR] UI registered: {name}")
                        continue

                # route messages
                if role == "ui":
                    # UI message -> forward to device
                    if DEVICE is not None:
                        try:
                            await DEVICE.send_str(json.dumps(data))
                        except Exception as e:
                            await ws.send_json({"error": "failed_to_send_to_device", "detail": str(e)})
                    else:
                        await ws.send_json({"error": "no_device_connected"})

                elif role == "device":
                    # Device message -> broadcast to UIs
                    await _broadcast_ui(data)

                else:
                    # Not registered yet — ask client to register
                    await ws.send_json({"error": "not_registered", "expect": {"type": "register", "role": "device|ui"}})

            elif msg.type == WSMsgType.ERROR:
                print('ws connection closed with exception %s' % ws.exception())

    finally:
        # cleanup
        if role == "device" and DEVICE is ws:
            DEVICE = None
            print("[MEDIATOR] Device disconnected")
        if role == "ui":
            UIS.discard(ws)
            print(f"[MEDIATOR] UI disconnected: {name}")

    return ws


async def _broadcast_ui(message):
    """Broadcast a Python object (dict/list) as JSON to all connected UIs."""
    to_remove = []
    text = json.dumps(message)
    for ui in list(UIS):
        try:
            await ui.send_str(text)
        except Exception:
            to_remove.append(ui)
    for u in to_remove:
        UIS.discard(u)


async def http_status(request):
    """POST /api/status -> broadcast to UIs. Useful as HTTP fallback."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)
    await _broadcast_ui({"type": "event", "event": "status", "payload": data})
    return web.json_response({"ok": True})


async def http_clients(request):
    return web.json_response({"device_connected": DEVICE is not None, "ui_count": len(UIS)})


def create_app():
    app = web.Application()
    app.router.add_get('/ws', ws_handler)
    app.router.add_post('/api/status', http_status)
    app.router.add_get('/api/clients', http_clients)
    return app


if __name__ == '__main__':
    app = create_app()
    print("Starting WS mediator on 0.0.0.0:3000 (ws -> /ws, http status -> /api/status)")
    web.run_app(app, host='0.0.0.0', port=3000)
