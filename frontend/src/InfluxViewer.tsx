import { useEffect, useState } from 'react'
import DailyCountersChart from './DailyCountersChart'

export default function InfluxViewer() {
  const [measurements, setMeasurements] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [points, setPoints] = useState<any[]>([])
  const [dailyPoints, setDailyPoints] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [measLoading, setMeasLoading] = useState(false)

  const fetchMeasurements = () => {
    setMeasLoading(true)
    fetch('http://127.0.0.1:4000/api/measurements')
      .then((r) => r.json())
      .then((j) => setMeasurements(j.measurements || []))
      .catch((e) => console.error(e))
      .finally(() => setMeasLoading(false))
  }

  useEffect(() => {
    fetchMeasurements()
    // Fetch the last 7 days of aggregated daily_counters for the chart
    fetch('http://127.0.0.1:4000/api/points?measurement=daily_counters&limit=7')
      .then((r) => r.json())
      .then((j) => {
        const pts = j.points || []
        // API returns newest-first; reverse to oldest-first for chart left->right
        setDailyPoints((pts || []).slice().reverse())
      })
      .catch((e) => console.error('daily counters fetch failed', e))
      .finally(() => {})
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    fetch(`http://127.0.0.1:4000/api/points?measurement=${encodeURIComponent(selected)}&limit=50`)
      .then((r) => r.json())
      .then((j) => setPoints(j.points || []))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false))
  }, [selected])

  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold">Last Week Trend</h2>
      {dailyPoints && dailyPoints.length > 0 && (
        <div className="mb-4">
          <DailyCountersChart points={dailyPoints} />
        </div>
      )}

      <h2 className="text-xl font-semibold">InfluxDB Viewer</h2>
      <div className="mt-2 flex gap-2 items-center">
        <button onClick={fetchMeasurements} className="border rounded px-2 py-1 bg-gray-100" disabled={measLoading}>
          {measLoading ? 'Refreshing...' : 'Refresh Measurements'}
        </button>
        <select value={selected || ''} onChange={(e) => setSelected(e.target.value)} className="border rounded px-2 py-1 flex-1">
          <option value="">-- select measurement --</option>
          {measurements.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div className="mt-4">
        {loading && <div>Loading...</div>}
        {!loading && selected && (
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm table-auto border-collapse">
              <thead>
                <tr>
                  {points[0] && Object.keys(points[0]).map((c) => (
                    <th key={c} className="border px-2 py-1 text-left">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {points.map((p, i) => (
                  <tr key={i} className="odd:bg-gray-50">
                    {Object.keys(points[0] || {}).map((c) => (
                      <td key={c} className="border px-2 py-1">{String(p[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
