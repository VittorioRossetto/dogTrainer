import ManualTrainerApp from "./ManualTrainerApp";
import InfluxViewer from "./InfluxViewer";

export default function App() {
  return (
    <div>
      <ManualTrainerApp />
      <div className="max-w-3xl mx-auto mt-6 mb-12">
        <InfluxViewer />
      </div>
    </div>
  );
}