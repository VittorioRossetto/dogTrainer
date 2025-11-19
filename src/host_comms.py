import threading
import time
import config
from flask import Flask, request, jsonify
import json
import asyncio
import requests
import websockets

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
            resp = requests.post(host_url, json=data, timeout=2)
            resp.raise_for_status()   

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
    if _send_via_ws(msg):
        print(f"[HOST][WS] Event broadcast: {event_type}")
        return

    # Fallback to HTTP POST if configured
    host_url = getattr(config, "HOST_URL", None)
    if host_url:
        try:
            resp = requests.post(host_url, json=msg, timeout=2)
            resp.raise_for_status()
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
    global _ws_server_loop, _ws_server_thread

    port = getattr(config, "WS_SERVER_PORT", 8765)
    path = getattr(config, "WS_SERVER_PATH", "/ws")

    async def _handler(ws, path_recv=None):
        # websockets library may call the handler with either (ws, path)
        # or with a single `connection` object. Accept either form and
        # extract the request path if needed.
        if path_recv is None:
            # WebSocketServerProtocol exposes the negotiated path as `.path`
            path_recv = getattr(ws, "path", None)

        # Only reject if we can determine the path and it doesn't match.
        # Some websockets versions call the handler with a single connection
        # object that may not expose the path immediately; in that case
        # allow the connection to proceed to avoid an immediate close.
        if path_recv is not None and path_recv != path:
            try:
                await ws.close()
            except Exception:
                pass
            return

        with _ws_clients_lock:
            _ws_clients.add(ws)
        # Debug: report connection details
        peer = getattr(ws, "remote_address", None)
        print(f"[HOST][WS] UI connected path={path_recv} peer={peer}")

        try:
            async for message in ws:
                # Expect text messages
                print(f"[HOST][WS] Message from {peer}: {message}")
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
        # Create the server from within the event loop to avoid
        # `asyncio.get_running_loop()` errors in newer websockets versions.
        async def _create_server():
            return await websockets.serve(_handler, '0.0.0.0', port)

        server = None
        try:
            server = loop.run_until_complete(_create_server())
            print(f"[HOST][WS] Server listening on 0.0.0.0:{port}{path}")
            loop.run_forever()
        finally:
            if server is not None:
                server.close()
                loop.run_until_complete(server.wait_closed())
            loop.close()

    _ws_server_thread = threading.Thread(target=_run_loop, daemon=True)
    _ws_server_thread.start()
    # done
