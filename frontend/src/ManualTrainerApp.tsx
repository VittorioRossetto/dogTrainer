import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function ManualTrainerApp() {
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [wsUrl, setWsUrl] = useState<string>(`ws://${window.location.hostname}:8765/ws`);
  const [mode, setMode] = useState<"auto" | "manual">("manual");
  const [audioText, setAudioText] = useState<string>("");
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = (msg: string) => setLogs((l) => [msg, ...l]);

  const handleConnect = () => {
    if (wsRef.current) return;
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        addLog(`WS connected: ${wsUrl}`);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          addLog(`Incoming: ${JSON.stringify(data)}`);
        } catch (e) {
          addLog(`Incoming: ${ev.data}`);
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        setConnected(false);
        addLog("WS disconnected");
      };

      ws.onerror = (e) => {
        addLog(`WS error`);
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

  const sendServoSweep = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      addLog("Not connected — cannot send servo");
      return;
    }
    const payload = { cmd: "servo", action: "sweep" };
    wsRef.current.send(JSON.stringify(payload));
    addLog("Servo sweep requested");
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

      <Card>
        <CardContent className="p-4 space-y-2">
          <Button onClick={handleConnect} disabled={connected}>
            {connected ? "Connected" : "Connect"}
          </Button>
          <div className="grid grid-cols-3 gap-2 pt-2">
            <Button onClick={() => sendCommand("sit")} disabled={!connected}>Sit</Button>
            <Button onClick={() => sendCommand("stand")} disabled={!connected}>Stand</Button>
            <Button onClick={() => sendCommand("lie")} disabled={!connected}>Lie</Button>
          </div>
          <Button onClick={dispense} variant="outline" disabled={!connected}>
            Dispense Treat
          </Button>
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
