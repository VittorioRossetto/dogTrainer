import threading
import time
import config
from flask import Flask, request, jsonify
import json
import asyncio

try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error
    _HAS_REQUESTS = False

try:
    import websockets
    _HAS_WS = True
except Exception:
    websockets = None
    _HAS_WS = False

# WebSocket server state
_ws_server_loop = None
_ws_server_thread = None
_ws_clients = set()
_ws_clients_lock = threading.Lock()
_command_handler = None

app = Flask(__name__)
latest_status = {}


@app.route("/status", methods=["POST"])
def receive_status():
    global latest_status
    latest_status = request.json
    return jsonify({"ok": True})


@app.route("/set_mode", methods=["POST"])
def set_mode():
    mode = request.json.get("mode")
    if mode in ["auto", "manual"]:
        config.MODE = mode
        print(f"[HOST] Mode switched to: {config.MODE}")
        return jsonify({"ok": True})
    return jsonify({"error": "invalid mode"}), 400


def run_server():
    app.run(host="0.0.0.0", port=5000)


def start_server():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    # Start websocket server (if configured)
    start_ws_server()


def register_command_handler(fn):
    """Register a callable that will receive incoming host commands (dict).
    The callable will be called with a single argument: the parsed JSON message.
    """
    global _command_handler
    _command_handler = fn


def send_status(data):
    global latest_status
    latest_status = data  # local caching
    # If a host URL is configured, attempt to POST the JSON status there.
    host_url = getattr(config, "HOST_URL", None)
    if host_url:
        try:
            if _HAS_REQUESTS:
                resp = requests.post(host_url, json=data, timeout=2)
                resp.raise_for_status()
            else:
                req = _urllib_request.Request(
                    host_url,
                    data=json.dumps(data).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _urllib_request.urlopen(req, timeout=2) as r:
                    # consume response (no-op)
                    r.read()

            print(f"[HOST] Status sent to host: {host_url}")
        except Exception as e:
            print(f"[HOST] Failed to send status to host {host_url}:", e)
            print("[HOST] Status cached locally:", data)
    else:
        # Fallback: only cache locally and print
        print("[HOST] Status updated (local only):", data)


def _send_via_ws(message: dict):
    """Send a JSON message to host over websocket if connected."""
    # Broadcast to all connected UI clients
    text = json.dumps(message)
    sent_any = False
    with _ws_clients_lock:
        clients = list(_ws_clients)

    for ws in clients:
        try:
            # websockets sends asynchronously; use `asyncio.run_coroutine_threadsafe`
            coro = ws.send(text)
            if _ws_server_loop is not None:
                asyncio.run_coroutine_threadsafe(coro, _ws_server_loop)
            else:
                # If loop not ready yet, schedule on default loop (best-effort)
                asyncio.get_event_loop().create_task(coro)
            sent_any = True
        except Exception as e:
            print("[HOST][WS] Failed sending to a client:", e)
    return sent_any


def send_event(event_type: str, payload: dict):
    """Convenience wrapper to send an event to host. Will try WS then HTTP.

    Event envelope: {"type": "event", "event": event_type, "timestamp": <float>, "payload": {...}}
    """
    msg = {
        "type": "event",
        "event": event_type,
        "timestamp": time.time(),
        "payload": payload,
    }

    # Try websocket first (broadcast to connected UIs)
    if _HAS_WS and _send_via_ws(msg):
        print(f"[HOST][WS] Event broadcast: {event_type}")
        return

    # Fallback to HTTP POST if configured
    host_url = getattr(config, "HOST_URL", None)
    if host_url:
        try:
            if _HAS_REQUESTS:
                resp = requests.post(host_url, json=msg, timeout=2)
                resp.raise_for_status()
            else:
                req = _urllib_request.Request(
                    host_url,
                    data=json.dumps(msg).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _urllib_request.urlopen(req, timeout=2) as r:
                    r.read()
            print(f"[HOST] Event posted to {host_url}: {event_type}")
        except Exception as e:
            print(f"[HOST] Failed to POST event to {host_url}:", e)
    else:
        print("[HOST] No host sink configured; event cached locally:", msg)


def start_ws_client():
    # Deprecated in server-hosting mode. kept for compatibility
    print("[HOST][WS] start_ws_client() deprecated when running server mode")


def start_ws_server():
    """Start an asyncio-based WebSocket server that accepts connections from UIs.

    Connected clients are added to `_ws_clients`. Incoming messages from UIs
    are dispatched to the registered command handler. Messages from the device
    (sent via `send_event`) are broadcast to UIs.
    """
    global _HAS_WS, _ws_server_loop, _ws_server_thread

    if not _HAS_WS:
        print("[HOST][WS] websockets package not available; WS server disabled")
        return

    port = getattr(config, "WS_SERVER_PORT", 8765)
    path = getattr(config, "WS_SERVER_PATH", "/ws")

    async def _handler(ws, path_recv):
        # Only accept connections on the configured path
        if path_recv != path:
            await ws.close()
            return

        with _ws_clients_lock:
            _ws_clients.add(ws)
        print("[HOST][WS] UI connected")

        try:
            async for message in ws:
                # Expect text messages
                try:
                    data = json.loads(message)
                except Exception:
                    print("[HOST][WS] Received non-JSON message from UI:", message)
                    continue

                # Dispatch to registered command handler if available
                if _command_handler:
                    try:
                        _command_handler(data)
                    except Exception as e:
                        print("[HOST][WS] Command handler error:", e)
                else:
                    print("[HOST][WS] No command handler registered. Message:", data)

        except Exception as e:
            print("[HOST][WS] Connection error:", e)
        finally:
            with _ws_clients_lock:
                _ws_clients.discard(ws)
            print("[HOST][WS] UI disconnected")

    def _run_loop():
        global _ws_server_loop
        loop = asyncio.new_event_loop()
        _ws_server_loop = loop
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(_handler, '0.0.0.0', port)
        server = loop.run_until_complete(start_server)
        print(f"[HOST][WS] Server listening on 0.0.0.0:{port}{path}")
        try:
            loop.run_forever()
        finally:
            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()

    _ws_server_thread = threading.Thread(target=_run_loop, daemon=True)
    _ws_server_thread.start()
    # done
