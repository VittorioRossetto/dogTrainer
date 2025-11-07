import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function ManualTrainerApp() {
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);

  const addLog = (msg: string) => setLogs((l) => [msg, ...l]);

  const handleConnect = () => {
    setConnected(true);
    addLog("Connected to trainer system.");
  };

  const sendCommand = (cmd: string) => {
    addLog(`Command sent: ${cmd}`);
  };

  const dispense = () => {
    addLog("Treat dispensed.");
  };

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
