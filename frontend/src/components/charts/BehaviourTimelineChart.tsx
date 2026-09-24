import React, { useState } from "react";
import type { BehaviourEvent } from "@/types";
import { formatBehaviourLabel } from "@/lib/utils";

const BEHAVIOUR_META: Record<string, { colour: string; bg: string; emoji: string }> = {
  viewing:                  { colour: "#6366f1", bg: "bg-indigo-500",  emoji: "👁" },
  touching:                 { colour: "#22c55e", bg: "bg-emerald-500", emoji: "✋" },
  picking:                  { colour: "#f59e0b", bg: "bg-amber-500",   emoji: "🛒" },
  picking_and_returning:    { colour: "#ef4444", bg: "bg-rose-500",    emoji: "↩️" },
  picking_and_putting_back: { colour: "#f97316", bg: "bg-orange-500",  emoji: "🔄" },
  no_interest_in_buying:    { colour: "#94a3b8", bg: "bg-slate-400",   emoji: "🚶" },
  turning_towards_shelf:    { colour: "#06b6d4", bg: "bg-cyan-500",    emoji: "↪️" },
};

export function BehaviourTimelineChart({ events }: { events: BehaviourEvent[] }) {
  const [hovered, setHovered] = useState<BehaviourEvent | null>(null);

  if (!events || events.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-2 text-slate-400">
        <div className="text-3xl">⏱️</div>
        <p className="text-sm">No timeline events yet — process a video first</p>
      </div>
    );
  }

  const maxTime = Math.max(...events.map((e) => e.end_time_seconds), 1);
  const trackIds = Array.from(new Set(events.map((e) => e.track_id))).sort((a, b) => a - b);

  // Tick marks every 10%
  const ticks = Array.from({ length: 11 }, (_, i) => (i / 10) * maxTime);

  return (
    <div className="space-y-4">
      {/* Tooltip */}
      {hovered && (
        <div className="fixed z-50 pointer-events-none rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-white shadow-2xl"
          style={{ top: 10, right: 10 }}
        >
          <p className="font-semibold">{formatBehaviourLabel(hovered.behaviour_type)}</p>
          <p className="text-slate-400">Customer #{hovered.track_id}</p>
          <p className="text-slate-400">{hovered.start_time_seconds.toFixed(1)}s → {hovered.end_time_seconds.toFixed(1)}s</p>
          <p className="text-slate-400">Zone: {hovered.shelf_zone || "—"}</p>
          <p className="text-slate-400">Confidence: {(hovered.confidence * 100).toFixed(0)}%</p>
        </div>
      )}

      {/* Time axis */}
      <div className="relative pl-28 pr-2">
        <div className="flex justify-between text-[10px] text-slate-400">
          {ticks.map((t) => <span key={t}>{t.toFixed(0)}s</span>)}
        </div>
      </div>

      {/* Swimlanes */}
      <div className="space-y-2 overflow-x-auto">
        {trackIds.map((trackId) => {
          const meta = BEHAVIOUR_META;
          return (
            <div key={trackId} className="flex items-center gap-3 group">
              <div className="w-24 shrink-0 flex items-center gap-1.5">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-[10px] font-bold text-white shadow-sm">
                  {trackId}
                </div>
                <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400">Person</span>
              </div>
              <div className="relative h-8 flex-1 min-w-[400px] rounded-lg bg-slate-100 dark:bg-slate-800/60 overflow-visible">
                {events
                  .filter((e) => e.track_id === trackId)
                  .map((e) => {
                    const left = (e.start_time_seconds / maxTime) * 100;
                    const width = Math.max(((e.end_time_seconds - e.start_time_seconds) / maxTime) * 100, 1.2);
                    const m = meta[e.behaviour_type] || meta.viewing;
                    return (
                      <div
                        key={e.id}
                        onMouseEnter={() => setHovered(e)}
                        onMouseLeave={() => setHovered(null)}
                        title={`${formatBehaviourLabel(e.behaviour_type)} ${e.start_time_seconds.toFixed(1)}s–${e.end_time_seconds.toFixed(1)}s`}
                        className="absolute top-1 h-6 rounded cursor-pointer transition-all hover:brightness-110 hover:scale-y-110 hover:z-10 flex items-center justify-center overflow-hidden"
                        style={{
                          left: `${left}%`,
                          width: `${width}%`,
                          background: m.colour,
                          opacity: 0.85,
                        }}
                      >
                        {width > 4 && (
                          <span className="text-[9px] text-white font-bold px-1 truncate select-none">
                            {e.behaviour_type === "no_interest_in_buying" ? "No Interest" :
                             e.behaviour_type === "picking_and_returning" ? "Pick+Return" :
                             e.behaviour_type === "picking_and_putting_back" ? "Pick+Put" :
                             formatBehaviourLabel(e.behaviour_type)}
                          </span>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 pt-1 border-t border-slate-100 dark:border-slate-800">
        {Object.entries(BEHAVIOUR_META).map(([key, m]) => (
          <div key={key} className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: m.colour }} />
            <span>{m.emoji} {formatBehaviourLabel(key)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
