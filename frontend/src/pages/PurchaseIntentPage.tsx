import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { PurchaseIntentGauge } from "@/components/charts/PurchaseIntentGauge";
import { getPredictionSummary, getPredictions } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import { JobRequired } from "./JobRequired";
import type { PurchaseIntentPrediction, PurchaseIntentSummary } from "@/types";
import { formatDuration } from "@/lib/utils";

function ScoreBar({ score }: { score: number }) {
  const colour = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
      <motion.div
        className={`h-full rounded-full ${colour}`}
        initial={{ width: 0 }}
        animate={{ width: `${score}%` }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      />
    </div>
  );
}

function IntentIcon({ label }: { label: string }) {
  if (label === "high") return <TrendingUp className="h-4 w-4 text-emerald-500" />;
  if (label === "medium") return <Minus className="h-4 w-4 text-amber-500" />;
  return <TrendingDown className="h-4 w-4 text-rose-500" />;
}

export default function PurchaseIntentPage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const navigate = useNavigate();
  const [summary, setSummary] = useState<PurchaseIntentSummary | null>(null);
  const [predictions, setPredictions] = useState<PurchaseIntentPrediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) { setLoading(false); return; }
    Promise.all([getPredictionSummary(jobId), getPredictions(jobId)])
      .then(([s, p]) => { setSummary(s); setPredictions(p); })
      .finally(() => setLoading(false));
  }, [jobId]);

  if (!jobId) return <DashboardLayout title="Purchase Intent"><JobRequired /></DashboardLayout>;

  const intentGroups = [
    { label: "High Intent", key: "high", count: summary?.high_intent_customers ?? 0, colour: "emerald", bg: "from-emerald-500 to-teal-500", emoji: "🔥" },
    { label: "Medium Intent", key: "medium", count: summary?.medium_intent_customers ?? 0, colour: "amber", bg: "from-amber-500 to-orange-400", emoji: "⚡" },
    { label: "Low Intent", key: "low", count: summary?.low_intent_customers ?? 0, colour: "rose", bg: "from-rose-500 to-pink-500", emoji: "❄️" },
  ];

  return (
    <DashboardLayout title="Purchase Intent">
      {/* Top section: gauge + breakdown */}
      <div className="grid gap-6 lg:grid-cols-3 mb-6">
        <Card className="lg:col-span-1 flex flex-col items-center justify-center py-6">
          <CardHeader><CardTitle className="text-center">🎯 Session Score</CardTitle></CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-48 w-48 rounded-full mx-auto" /> : (
              <PurchaseIntentGauge score={summary?.average_score ?? 0} />
            )}
            <p className="text-xs text-slate-400 text-center mt-3">Average across {summary?.total_customers ?? 0} customers</p>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-4 content-center">
          {intentGroups.map((g, i) => (
            <motion.div
              key={g.key}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 text-center relative overflow-hidden"
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${g.bg} opacity-5`} />
              <div className="text-3xl mb-2">{g.emoji}</div>
              <div className="text-4xl font-extrabold text-slate-900 dark:text-white">
                {loading ? "—" : g.count}
              </div>
              <div className="text-xs text-slate-400 mt-1">{g.label}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Per-customer cards */}
      <Card>
        <CardHeader><CardTitle>👤 Per-Customer Predictions</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
          ) : predictions.length === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center">No predictions available yet.</p>
          ) : (
            <div className="space-y-3">
              {predictions.map((p, i) => (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.4) }}
                  className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-sm font-bold shadow shrink-0">
                      {p.track_id}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-slate-900 dark:text-white">Person #{p.track_id}</span>
                        <IntentIcon label={p.intent_label} />
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ml-auto ${
                          p.intent_label === "high" ? "bg-emerald-500/15 text-emerald-500" :
                          p.intent_label === "medium" ? "bg-amber-500/15 text-amber-500" :
                          "bg-rose-500/15 text-rose-500"
                        }`}>{p.intent_label.toUpperCase()} · {p.purchase_intent_score.toFixed(0)}/100</span>
                      </div>
                      <ScoreBar score={p.purchase_intent_score} />
                    </div>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    {[
                      { label: "Dwell", value: formatDuration(p.dwell_time_seconds) },
                      { label: "Touches", value: p.touch_count },
                      { label: "Picks", value: p.pick_count },
                      { label: "Returns", value: p.return_count },
                    ].map((m) => (
                      <div key={m.label} className="rounded-xl bg-slate-50 dark:bg-slate-800 py-2">
                        <div className="font-bold text-sm text-slate-800 dark:text-white">{m.value}</div>
                        <div className="text-[10px] text-slate-400">{m.label}</div>
                      </div>
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-3 mt-4">
        <Button className="flex-1" onClick={() => navigate("/recommendations")}>
          AI Recommendations <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
        <Button variant="outline" className="flex-1" onClick={() => navigate("/reports")}>
          View Reports <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </DashboardLayout>
  );
}
