import React from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { BehaviourDistributionItem } from "@/types";
import { formatBehaviourLabel } from "@/lib/utils";

const COLOURS = [
  "#6366f1", "#22c55e", "#f59e0b", "#ef4444",
  "#06b6d4", "#a855f7", "#ec4899",
];

const RADIAN = Math.PI / 180;

function CustomLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) {
  if (percent < 0.05) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.55;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={700}>
      {(percent * 100).toFixed(0)}%
    </text>
  );
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div className="rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-white shadow-xl">
      <p className="font-semibold mb-0.5">{d.name}</p>
      <p className="text-slate-300">{d.value} events</p>
    </div>
  );
}

export function BehaviourDistributionChart({ data }: { data: BehaviourDistributionItem[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-slate-400">
        <div className="h-16 w-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-2xl">📊</div>
        <p className="text-sm">No behaviour data yet — process a video first</p>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    name: formatBehaviourLabel(d.behaviour_type),
    value: d.count,
    pct: d.percentage,
  }));

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={105}
            paddingAngle={3}
            labelLine={false}
            label={CustomLabel}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLOURS[i % COLOURS.length]} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="grid grid-cols-2 gap-2">
        {chartData.map((d, i) => (
          <div key={d.name} className="flex items-center gap-2 text-xs">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: COLOURS[i % COLOURS.length] }} />
            <span className="text-slate-600 dark:text-slate-400 truncate">{d.name}</span>
            <span className="ml-auto font-medium text-slate-900 dark:text-white">{d.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
