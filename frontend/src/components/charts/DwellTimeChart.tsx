import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell,
} from "recharts";
import type { PurchaseIntentPrediction } from "@/types";

const intentGradient = (score: number) =>
  score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-white shadow-xl">
      <p className="font-semibold mb-1">{d.name}</p>
      <p className="text-slate-300">Dwell: <span className="text-white font-medium">{d.dwell}s</span></p>
      <p className="text-slate-300">Intent score: <span className="font-medium" style={{ color: intentGradient(d.score) }}>{d.score}</span></p>
    </div>
  );
}

export function DwellTimeChart({ data }: { data: PurchaseIntentPrediction[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-slate-400">
        <div className="text-3xl">⏳</div>
        <p className="text-sm">No customer data yet</p>
      </div>
    );
  }

  const chartData = data
    .slice()
    .sort((a, b) => b.dwell_time_seconds - a.dwell_time_seconds)
    .slice(0, 10)
    .map((d) => ({
      name: `#${d.track_id}`,
      dwell: Math.round(d.dwell_time_seconds),
      score: d.purchase_intent_score,
    }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#33415533" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} unit="s" />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 12, fill: "#94a3b8", fontWeight: 600 }}
          width={36}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="dwell" radius={[0, 8, 8, 0]} maxBarSize={22}>
          {chartData.map((d, i) => (
            <Cell key={i} fill={intentGradient(d.score)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
