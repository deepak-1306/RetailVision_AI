import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Clock, Users, Filter, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { BehaviourTimelineChart } from "@/components/charts/BehaviourTimelineChart";
import { getBehaviourTimeline } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import { JobRequired } from "./JobRequired";
import type { BehaviourEvent } from "@/types";
import { formatBehaviourLabel } from "@/lib/utils";

const BEHAVIOUR_COLOURS: Record<string, string> = {
  viewing: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
  touching: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  picking: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  picking_and_returning: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  picking_and_putting_back: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  no_interest_in_buying: "bg-slate-500/15 text-slate-400 border-slate-500/30",
  turning_towards_shelf: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
};

const BEHAVIOUR_EMOJIS: Record<string, string> = {
  viewing: "👁",
  touching: "✋",
  picking: "🛒",
  picking_and_returning: "↩️",
  picking_and_putting_back: "🔄",
  no_interest_in_buying: "🚶",
  turning_towards_shelf: "↪️",
};

export default function TimelinePage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const navigate = useNavigate();
  const [events, setEvents] = useState<BehaviourEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string>("all");

  useEffect(() => {
    if (!jobId) { setLoading(false); return; }
    getBehaviourTimeline(jobId).then(setEvents).finally(() => setLoading(false));
  }, [jobId]);

  if (!jobId) {
    return <DashboardLayout title="Behaviour Timeline"><JobRequired /></DashboardLayout>;
  }

  const behaviourTypes = Array.from(new Set(events.map((e) => e.behaviour_type)));
  const filtered = activeFilter === "all" ? events : events.filter((e) => e.behaviour_type === activeFilter);
  const totalCustomers = new Set(events.map((e) => e.track_id)).size;

  return (
    <DashboardLayout title="Behaviour Timeline">
      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Events", value: loading ? "—" : events.length, emoji: "📋" },
          { label: "Unique Customers", value: loading ? "—" : totalCustomers, emoji: "👥" },
          { label: "Behaviour Types", value: loading ? "—" : behaviourTypes.length, emoji: "🏷️" },
          { label: "Duration", value: loading ? "—" : events.length ? `${Math.max(...events.map(e => e.end_time_seconds)).toFixed(0)}s` : "0s", emoji: "⏱️" },
        ].map((s) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 text-center"
          >
            <div className="text-2xl mb-1">{s.emoji}</div>
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{s.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Timeline chart */}
      <Card className="mb-6">
        <CardHeader className="flex flex-row items-center gap-2">
          <Clock className="h-4 w-4 text-indigo-500" />
          <CardTitle>Customer Behaviour Swimlane Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? <Skeleton className="h-64 w-full" /> : <BehaviourTimelineChart events={events} />}
        </CardContent>
      </Card>

      {/* Event log with filter */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <CardTitle>Event Log</CardTitle>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setActiveFilter("all")}
              className={`rounded-full px-3 py-1 text-xs font-medium border transition-all ${
                activeFilter === "all" ? "bg-indigo-500 text-white border-indigo-500" : "border-slate-200 dark:border-slate-700 text-slate-500 hover:border-indigo-400"
              }`}
            >All</button>
            {behaviourTypes.map((b) => (
              <button
                key={b}
                onClick={() => setActiveFilter(b)}
                className={`rounded-full px-3 py-1 text-xs font-medium border transition-all ${
                  activeFilter === b
                    ? "bg-indigo-500 text-white border-indigo-500"
                    : "border-slate-200 dark:border-slate-700 text-slate-500 hover:border-indigo-400"
                }`}
              >
                {BEHAVIOUR_EMOJIS[b]} {formatBehaviourLabel(b)}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-slate-400 py-8 text-center">No events match this filter.</p>
          ) : (
            <div className="max-h-96 overflow-y-auto space-y-1.5 scrollbar-thin pr-1">
              {filtered.map((e, i) => (
                <motion.div
                  key={e.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(i * 0.01, 0.3) }}
                  className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 ${BEHAVIOUR_COLOURS[e.behaviour_type] || BEHAVIOUR_COLOURS.viewing}`}
                >
                  <span className="text-base">{BEHAVIOUR_EMOJIS[e.behaviour_type] || "📍"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">Customer #{e.track_id}</span>
                      <span className="text-xs opacity-80">{formatBehaviourLabel(e.behaviour_type)}</span>
                    </div>
                    <div className="text-xs opacity-60 mt-0.5">
                      {e.start_time_seconds.toFixed(1)}s → {e.end_time_seconds.toFixed(1)}s
                      {e.shelf_zone ? ` · Zone: ${e.shelf_zone}` : ""}
                    </div>
                  </div>
                  <div className="text-right text-xs opacity-70">
                    <div>{((e.end_time_seconds - e.start_time_seconds)).toFixed(1)}s</div>
                    <div>{(e.confidence * 100).toFixed(0)}% conf</div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-3 mt-4">
        <Button className="flex-1" onClick={() => navigate("/analytics")}>
          Customer Analytics <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
        <Button variant="outline" className="flex-1" onClick={() => navigate("/purchase-intent")}>
          Purchase Intent <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </DashboardLayout>
  );
}
