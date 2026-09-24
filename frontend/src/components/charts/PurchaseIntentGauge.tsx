import React from "react";
import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from "recharts";

function scoreColour(score: number) {
  if (score >= 70) return { fill: "#22c55e", label: "High Intent", ring: "stroke-emerald-500" };
  if (score >= 40) return { fill: "#f59e0b", label: "Medium Intent", ring: "stroke-amber-500" };
  return { fill: "#ef4444", label: "Low Intent", ring: "stroke-rose-500" };
}

export function PurchaseIntentGauge({ score }: { score: number }) {
  const { fill, label } = scoreColour(score);
  const data = [{ name: "score", value: Math.round(score), fill }];

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative flex items-center justify-center w-48 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="68%"
            outerRadius="100%"
            barSize={16}
            data={data}
            startAngle={90}
            endAngle={-270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar
              background={{ fill: "#e2e8f0" }}
              dataKey="value"
              cornerRadius={10}
            />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute flex flex-col items-center pointer-events-none">
          <span className="text-4xl font-extrabold text-slate-900 dark:text-white leading-none">
            {Math.round(score)}
          </span>
          <span className="text-xs text-slate-400 mt-1">/ 100</span>
        </div>
      </div>
      <span
        className="rounded-full px-3 py-0.5 text-xs font-semibold"
        style={{ background: fill + "22", color: fill }}
      >
        {label}
      </span>
    </div>
  );
}
