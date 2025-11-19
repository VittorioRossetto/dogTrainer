# api_server.py
from flask import Flask, request, jsonify
from threading import Thread

def create_api(state, command_queue):
    """
    state: object with attribute 'mode' (string: 'auto'|'manual')
    command_queue: queue.Queue() into which host commands are placed
    """
    app = Flask("control_api")

    @app.route("/mode", methods=["GET","POST"])
    def mode():
        if request.method == "GET":
            return jsonify({"mode": state["mode"]})
        body = request.get_json(force=True)
        mode = body.get("mode")
        if mode in ("auto","manual"):
            state["mode"] = mode
            return jsonify({"ok": True, "mode": state["mode"]})
        return jsonify({"error":"invalid mode"}), 400

    @app.route("/command", methods=["POST"])
    def command():
        # expects JSON {"type":"servo"|"audio", "action":..., ...}
        body = request.get_json(force=True)
        # push command to main via queue
        command_queue.put(body)
        return jsonify({"ok": True})

    return app

def run_api_in_thread(state, command_queue, host="0.0.0.0", port=5000):
    app = create_api(state, command_queue)
    thread = Thread(target=lambda: app.run(host=host, port=port, threaded=True), daemon=True)
    thread.start()
    return thread
