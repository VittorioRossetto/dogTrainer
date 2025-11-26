import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function ManualTrainerApp() {
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  /* Choose `ws` or `wss` automatically depending on page protocol to
   avoid mixed-content blocks when the frontend is served over HTTPS. */
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const defaultHost = "raspberrypi.local";
  const defaultWsUrl = `${proto}://${defaultHost}:8765/ws`;
  const [wsUrl, setWsUrl] = useState<string>(defaultWsUrl);
  const [mode, setMode] = useState<"auto" | "manual">("manual");
  const [audioText, setAudioText] = useState<string>("");
  const [fileToSend, setFileToSend] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [successCount, setSuccessCount] = useState<number>(0);
  const [treatCount, setTreatCount] = useState<number>(0);
  const [, setRecentSuccesses] = useState<Array<{ target_pose?: string; when: number; filename?: string; text?: string }>>([]);
  const [highlightSuccess, setHighlightSuccess] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = (msg: string) => setLogs((l) => [msg, ...l]);

  const handleConnect = () => {
    if (wsRef.current) return;
    try {
      // Recompute proto/host at connect time in case the page context changed.
      const connectProto = window.location.protocol === "https:" ? "wss" : "ws";
      const connectHost = window.location.hostname || defaultHost;
      const connectUrl = wsUrl || `${connectProto}://${connectHost}:8765/ws`;
      addLog(`Connecting to ${connectUrl}`);
      const ws = new WebSocket(connectUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        addLog(`WS connected: ${connectUrl}`);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          addLog(`Incoming: ${JSON.stringify(data)}`);

          // Handle event envelopes from device/collector
          if (data && data.type === 'event') {
            const evName = data.event;
            const payload = data.payload || {};
            if (evName === 'command_success') {
              // increment local counter and flash UI
              setSuccessCount((s) => s + 1);
              setRecentSuccesses((rs) => [{ target_pose: payload.target_pose, when: Date.now(), filename: payload.filename, text: payload.command_text }, ...rs].slice(0, 10));
              setHighlightSuccess(true);
              // clear highlight after 3s
              setTimeout(() => setHighlightSuccess(false), 3000);
            }

            if (evName === 'treat_given') {
              setTreatCount((t) => t + 1);
              // Treats given by automatic mode count as successful commands as well
              try {
                const reason = (payload && payload.reason) ? String(payload.reason).toLowerCase() : '';
                if (reason === 'auto') {
                  setSuccessCount((s) => s + 1);
                  setRecentSuccesses((rs) => [{ target_pose: undefined, when: Date.now(), filename: undefined, text: 'treat:auto' }, ...rs].slice(0, 10));
                  setHighlightSuccess(true);
                  setTimeout(() => setHighlightSuccess(false), 3000);
                }
              } catch (e) {
                // ignore malformed payloads
              }
            }
          }
        } catch (e) {
          addLog(`Incoming: ${ev.data}`);
        }
      };

      ws.onclose = (ev) => {
        wsRef.current = null;
        setConnected(false);
        addLog(`WS disconnected (code=${ev.code} reason=${ev.reason})`);
      };

      ws.onerror = (e) => {
        // `onerror` provides limited info; log a helpful message and
        // rely on onclose for the actual close code.
        addLog(`WS error: ${String((e as any).message || e)}`);
        console.error("WebSocket error", e);
      };
    } catch (e) {
      addLog(`Failed to connect: ${String(e)}`);
    }
  };

  const sendCommand = (cmd: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      addLog("Not connected — cannot send command");
      return;
    }

    // For simple pose commands, send as `audio` so device will speak instruction.
    const payload = { cmd: "audio", text: cmd };
    wsRef.current.send(JSON.stringify(payload));
    addLog(`Command sent: ${JSON.stringify(payload)}`);
  };

  const dispense = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      addLog("Not connected — cannot dispense");
      return;
    }
    // Ask device to perform treat/take action
    const payload = { cmd: "treat_now" };
    wsRef.current.send(JSON.stringify(payload));
    addLog("Treat dispense requested");
  };

  const setModeCmd = (m: "auto" | "manual") => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      addLog("Not connected — cannot change mode");
      return;
    }
    const payload = { cmd: "set_mode", mode: m };
    wsRef.current.send(JSON.stringify(payload));
    setMode(m);
    addLog(`Mode change requested: ${m}`);
  };

  const sendAudio = () => {
    if (!audioText) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      addLog("Not connected — cannot send audio");
      return;
    }
    const payload = { cmd: "audio", text: audioText };
    wsRef.current.send(JSON.stringify(payload));
    addLog(`Audio requested: ${audioText}`);
    setAudioText("");
  };

  const sendRecording = () => {
    if (!fileToSend) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      addLog("Not connected — cannot send recording");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // result is like: data:audio/wav;base64,AAAA...
      const parts = result.split(",");
      const b64 = parts.length > 1 ? parts[1] : parts[0];
      const payload = { cmd: "audio", b64, filename: fileToSend.name };
      wsRef.current!.send(JSON.stringify(payload));
      addLog(`Recording sent: ${fileToSend.name}`);
      setFileToSend(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    };
    reader.onerror = (e) => {
      addLog(`Failed to read file: ${String(e)}`);
    };
    reader.readAsDataURL(fileToSend);
  };

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return (
    <div className="p-4 grid gap-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold">Dog Trainer Manual Control</h1>

      <div className="flex gap-4 items-center">
        <div className={`px-3 py-1 rounded ${highlightSuccess ? 'bg-green-200 animate-pulse' : 'bg-gray-100'}`}>
          <strong>Successes:</strong> {successCount}
        </div>
        <div className="px-3 py-1 rounded bg-gray-100">
          <strong>Treats:</strong> {treatCount}
        </div>
        <button
          onClick={() => {
            // fetch latest daily_counters from influx API
            fetch('http://127.0.0.1:4000/api/points?measurement=daily_counters&limit=1')
              .then((r) => r.json())
              .then((j) => {
                const p = (j.points && j.points[0]) || null;
                if (p) {
                  if (p.command_success_count != null) setSuccessCount(Number(p.command_success_count));
                  if (p.treat_count != null) setTreatCount(Number(p.treat_count));
                }
              })
              .catch((e) => addLog(`Failed to fetch counters: ${String(e)}`));
          }}
          className="border rounded px-2 py-1 bg-white"
        >
          Load Counters
        </button>
      </div>

      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center gap-2">
            <input
              className="border rounded px-2 py-1 flex-1"
              value={wsUrl}
              onChange={(e) => setWsUrl(e.target.value)}
              placeholder={defaultWsUrl}
              aria-label="WebSocket URL"
            />
            <Button onClick={handleConnect} disabled={connected}>
              {connected ? "Connected" : "Connect"}
            </Button>
          </div>
          <div className="grid grid-cols-3 gap-2 pt-2">
            <Button onClick={() => sendCommand("sit")} disabled={!connected}>Sit</Button>
            <Button onClick={() => sendCommand("stand")} disabled={!connected}>Stand</Button>
            <Button onClick={() => sendCommand("lie")} disabled={!connected}>Lie</Button>
          </div>
          <Button onClick={dispense} variant="outline" disabled={!connected}>
            Dispense Treat
          </Button>

          <div className="pt-2 flex items-center gap-2">
            <span className="text-sm">Mode:</span>
            <Button
              onClick={() => setModeCmd("auto")}
              disabled={!connected || mode === "auto"}
              variant={mode === "auto" ? undefined : "outline"}
            >
              Auto
            </Button>
            <Button
              onClick={() => setModeCmd("manual")}
              disabled={!connected || mode === "manual"}
              variant={mode === "manual" ? undefined : "outline"}
            >
              Manual
            </Button>
          </div>

          {/* Custom audio input */}
          <div className="pt-2 flex gap-2">
            <input
              className="border rounded px-2 py-1 flex-1"
              placeholder="Type audio text (e.g. 'Good dog!')"
              value={audioText}
              onChange={(e) => setAudioText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') sendAudio(); }}
              aria-label="Audio text"
            />
            <Button onClick={sendAudio} disabled={!connected || !audioText}>
              Send Audio
            </Button>
          </div>

          {/* Upload/Send recorded audio */}
          <div className="pt-2 flex gap-2 items-center">
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={(e) => setFileToSend(e.target.files ? e.target.files[0] : null)}
              aria-label="Upload recording"
            />
            <Button onClick={sendRecording} disabled={!connected || !fileToSend}>
              Send Recording
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 space-y-2 h-64 overflow-y-auto">
          <h2 className="text-xl font-semibold">Logs</h2>
          <ul className="text-sm space-y-1">
            {logs.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
