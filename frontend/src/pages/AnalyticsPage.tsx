import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users, Clock, Hand, ShoppingBag, ChevronRight, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { BehaviourDistributionChart } from "@/components/charts/BehaviourDistributionChart";
import { DwellTimeChart } from "@/components/charts/DwellTimeChart";
import { getBehaviourDistribution, getCustomerJourney, getPredictions } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import { JobRequired } from "./JobRequired";
import type { BehaviourDistributionItem, CustomerJourneyItem, PurchaseIntentPrediction } from "@/types";
import { formatDuration, formatBehaviourLabel } from "@/lib/utils";

const BEHAVIOUR_CHIP_COLOURS: Record<string, string> = {
  viewing: "bg-indigo-500/15 text-indigo-500 border-indigo-400/30",
  touching: "bg-emerald-500/15 text-emerald-500 border-emerald-400/30",
  picking: "bg-amber-500/15 text-amber-500 border-amber-400/30",
  picking_and_returning: "bg-rose-500/15 text-rose-500 border-rose-400/30",
  picking_and_putting_back: "bg-orange-500/15 text-orange-500 border-orange-400/30",
  no_interest_in_buying: "bg-slate-500/15 text-slate-500 border-slate-400/30",
  turning_towards_shelf: "bg-cyan-500/15 text-cyan-500 border-cyan-400/30",
};

const EMOJIS: Record<string, string> = {
  viewing: "👁", touching: "✋", picking: "🛒",
  picking_and_returning: "↩️", picking_and_putting_back: "🔄",
  no_interest_in_buying: "🚶", turning_towards_shelf: "↪️",
};

function intentBadge(score: number) {
  if (score >= 70) return "bg-emerald-500/15 text-emerald-500";
  if (score >= 40) return "bg-amber-500/15 text-amber-500";
  return "bg-rose-500/15 text-rose-500";
}

export default function AnalyticsPage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const navigate = useNavigate();
  const [distribution, setDistribution] = useState<BehaviourDistributionItem[]>([]);
  const [journeys, setJourneys] = useState<CustomerJourneyItem[]>([]);
  const [predictions, setPredictions] = useState<PurchaseIntentPrediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) { setLoading(false); return; }
    Promise.all([getBehaviourDistribution(jobId), getCustomerJourney(jobId), getPredictions(jobId)])
      .then(([d, j, p]) => { setDistribution(d); setJourneys(j); setPredictions(p); })
      .finally(() => setLoading(false));
  }, [jobId]);

  if (!jobId) return <DashboardLayout title="Customer Analytics"><JobRequired /></DashboardLayout>;

  const totalCustomers = journeys.length;
  const avgDwell = journeys.length ? journeys.reduce((a, j) => a + j.total_dwell_seconds, 0) / journeys.length : 0;
  const totalTouches = predictions.reduce((a, p) => a + p.touch_count, 0);
  const totalPicks = predictions.reduce((a, p) => a + p.pick_count, 0);

  const stats = [
    { label: "Unique Customers", value: totalCustomers, icon: "👥", colour: "from-indigo-500 to-purple-600" },
    { label: "Avg. Dwell Time", value: formatDuration(avgDwell), icon: "⏱️", colour: "from-amber-500 to-orange-500" },
    { label: "Total Touches", value: totalTouches, icon: "✋", colour: "from-emerald-500 to-teal-500" },
    { label: "Total Picks", value: totalPicks, icon: "🛒", colour: "from-rose-500 to-pink-600" },
  ];

  return (
    <DashboardLayout title="Customer Analytics">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
            className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 overflow-hidden relative"
          >
            <div className={`absolute inset-0 opacity-5 bg-gradient-to-br ${s.colour}`} />
            <div className="text-2xl mb-2">{s.icon}</div>
            <div className="text-2xl font-extrabold text-slate-900 dark:text-white">{loading ? "—" : s.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2 mb-6">
        <Card>
          <CardHeader><CardTitle>🏷️ Behaviour Distribution</CardTitle></CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-64" /> : <BehaviourDistributionChart data={distribution} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>⏳ Dwell Time by Customer</CardTitle></CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-64" /> : <DwellTimeChart data={predictions} />}
          </CardContent>
        </Card>
      </div>

      {/* Customer journey cards */}
      <Card>
        <CardHeader><CardTitle>🗺️ Customer Journeys</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-32 w-full" />)}
            </div>
          ) : journeys.length === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center">No customer journeys recorded yet.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {journeys.map((j, idx) => {
                const pred = predictions.find((p) => p.track_id === j.track_id);
                const score = pred?.purchase_intent_score ?? 0;
                return (
                  <motion.div
                    key={j.track_id}
                    initial={{ opacity: 0, scale: 0.97 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: idx * 0.04 }}
                    className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shadow">
                          {j.track_id}
                        </div>
                        <div>
                          <p className="font-semibold text-sm text-slate-800 dark:text-white">Person #{j.track_id}</p>
                          <p className="text-[10px] text-slate-400">{j.events.length} events</p>
                        </div>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${intentBadge(score)}`}>
                        {score.toFixed(0)}/100
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <span>⏱️</span>
                      <span>{formatDuration(j.total_dwell_seconds)} dwell</span>
                    </div>

                    <div className="flex flex-wrap gap-1">
                      {Array.from(new Set(j.events.map((e) => e.behaviour_type))).map((b) => (
                        <span
                          key={b}
                          className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${BEHAVIOUR_CHIP_COLOURS[b] || BEHAVIOUR_CHIP_COLOURS.viewing}`}
                        >
                          {EMOJIS[b]} {formatBehaviourLabel(b)}
                        </span>
                      ))}
                    </div>

                    {/* Mini timeline */}
                    {j.events.length > 0 && (() => {
                      const maxT = Math.max(...j.events.map(e => e.end_time_seconds), 1);
                      return (
                        <div className="relative h-3 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                          {j.events.map((e) => {
                            const colourMap: Record<string, string> = {
                              viewing: "#6366f1", touching: "#22c55e", picking: "#f59e0b",
                              picking_and_returning: "#ef4444", picking_and_putting_back: "#f97316",
                              no_interest_in_buying: "#94a3b8", turning_towards_shelf: "#06b6d4",
                            };
                            return (
                              <div
                                key={e.id}
                                className="absolute top-0 h-full opacity-80"
                                style={{
                                  left: `${(e.start_time_seconds / maxT) * 100}%`,
                                  width: `${Math.max(((e.end_time_seconds - e.start_time_seconds) / maxT) * 100, 2)}%`,
                                  background: colourMap[e.behaviour_type] || "#6366f1",
                                }}
                              />
                            );
                          })}
                        </div>
                      );
                    })()}
                  </motion.div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-3 mt-4">
        <Button className="flex-1" onClick={() => navigate("/purchase-intent")}>
          Purchase Intent <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
        <Button variant="outline" className="flex-1" onClick={() => navigate("/recommendations")}>
          AI Recommendations <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </DashboardLayout>
  );
}
