import ManualTrainerApp from "./ManualTrainerApp";
import InfluxViewer from "./InfluxViewer";

export default function App() {
  return (
    <div>
      <ManualTrainerApp />
      <div className="max-w-3xl mx-auto mt-6">
        <InfluxViewer />
      </div>
    </div>
  );
}