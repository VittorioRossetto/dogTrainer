import React from 'react'

export default function DailyCountersChart({ points }: { points: Array<any> }) {
  // Expect points: [{date: 'YYYY-MM-DD', command_success_count: N, treat_count: M}, ...]
  const width = 700
  const height = 220
  const margin = { top: 10, right: 10, bottom: 50, left: 40 }
  const innerW = width - margin.left - margin.right
  const innerH = height - margin.top - margin.bottom

  const successVals = points.map((p) => Number(p.command_success_count || 0))
  const treatVals = points.map((p) => Number(p.treat_count || 0))
  const maxVal = Math.max(1, ...successVals, ...treatVals)
  const n = points.length || 1
  const band = innerW / n
  const barWidth = Math.max(6, Math.floor(band * 0.35))

  return (
    <div className="overflow-x-auto">
      <svg width={Math.min(width, 900)} height={height}>
        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Y grid + labels */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const y = innerH - t * innerH
            const v = Math.round(t * maxVal)
            return (
              <g key={t}>
                <line x1={0} x2={innerW} y1={y} y2={y} stroke="#eee" />
                <text x={-8} y={y + 4} textAnchor="end" fontSize={10} fill="#666">{v}</text>
              </g>
            )
          })}

          {/* Bars */}
          {points.map((p, i) => {
            const sx = i * band + band * 0.2
            const sH = Math.round((Number(p.command_success_count || 0) / maxVal) * innerH)
            const tH = Math.round((Number(p.treat_count || 0) / maxVal) * innerH)
            return (
              <g key={p.date}>
                {/* success bar (green) */}
                <rect x={sx} y={innerH - sH} width={barWidth} height={sH} fill="#16a34a" rx={2} />
                {/* treat bar (orange) */}
                <rect x={sx + barWidth + 4} y={innerH - tH} width={barWidth} height={tH} fill="#f97316" rx={2} />
                {/* x label */}
                <text x={sx + barWidth} y={innerH + 14} textAnchor="middle" fontSize={10} fill="#333">{p.date}</text>
              </g>
            )
          })}

          {/* Legend */}
          <g transform={`translate(${innerW - 160},0)`}>
            <rect x={0} y={0} width={12} height={12} fill="#16a34a" />
            <text x={18} y={10} fontSize={12} fill="#333">Successes</text>
            <rect x={0} y={18} width={12} height={12} fill="#f97316" />
            <text x={18} y={30} fontSize={12} fill="#333">Treats</text>
          </g>
        </g>
      </svg>
    </div>
  )
}
