import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Lightbulb, Users, ChevronRight, AlertTriangle, Zap, ArrowUpCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { getRecommendations } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import { JobRequired } from "./JobRequired";
import type { Recommendation } from "@/types";

const PRIORITY_META: Record<string, { label: string; colour: string; bg: string; border: string; icon: React.ReactNode; gradient: string }> = {
  critical: { label: "Critical", colour: "text-rose-500", bg: "bg-rose-500/10", border: "border-rose-500/40", icon: <AlertTriangle className="h-5 w-5 text-rose-500" />, gradient: "from-rose-500 to-pink-600" },
  high:     { label: "High",     colour: "text-orange-500", bg: "bg-orange-500/10", border: "border-orange-400/40", icon: <ArrowUpCircle className="h-5 w-5 text-orange-500" />, gradient: "from-orange-500 to-amber-500" },
  medium:   { label: "Medium",   colour: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-400/40", icon: <Zap className="h-5 w-5 text-amber-500" />, gradient: "from-amber-400 to-yellow-400" },
  low:      { label: "Low",      colour: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-400/40", icon: <Lightbulb className="h-5 w-5 text-emerald-500" />, gradient: "from-emerald-500 to-teal-500" },
};

function getPriorityMeta(priority: string) {
  return PRIORITY_META[priority?.toLowerCase()] || PRIORITY_META.low;
}

export default function RecommendationsPage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const navigate = useNavigate();
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) { setLoading(false); return; }
    getRecommendations(jobId).then(setRecs).finally(() => setLoading(false));
  }, [jobId]);

  if (!jobId) return <DashboardLayout title="AI Recommendations"><JobRequired /></DashboardLayout>;

  const critical = recs.filter((r) => r.priority?.toLowerCase() === "critical").length;
  const high = recs.filter((r) => r.priority?.toLowerCase() === "high").length;

  return (
    <DashboardLayout title="AI Recommendations">
      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Actions", value: recs.length, emoji: "💡" },
          { label: "Critical", value: critical, emoji: "🚨" },
          { label: "High Priority", value: high, emoji: "⬆️" },
          { label: "Zones Affected", value: new Set(recs.map(r => r.shelf_zone).filter(Boolean)).size, emoji: "🗺️" },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 text-center"
          >
            <div className="text-2xl mb-1">{s.emoji}</div>
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{loading ? "—" : s.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Recommendation cards */}
      {loading ? (
        <div className="space-y-4">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 w-full" />)}</div>
      ) : recs.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <div className="text-5xl mb-4">🎯</div>
            <p className="text-slate-400">No recommendations generated for this session yet.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {recs.map((r, i) => {
            const meta = getPriorityMeta(r.priority);
            return (
              <motion.div
                key={r.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                <div className={`rounded-2xl border ${meta.border} ${meta.bg} p-5 relative overflow-hidden`}>
                  {/* Left accent bar */}
                  <div className={`absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b ${meta.gradient}`} />

                  <div className="pl-3">
                    <div className="flex items-start gap-4">
                      {/* Icon */}
                      <div className={`h-11 w-11 shrink-0 rounded-xl ${meta.bg} flex items-center justify-center border ${meta.border}`}>
                        {meta.icon}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <h3 className="font-bold text-slate-900 dark:text-white text-base">{r.title}</h3>
                          <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${meta.bg} ${meta.colour} border ${meta.border}`}>
                            {meta.label}
                          </span>
                          {r.shelf_zone && (
                            <span className="rounded-full px-2.5 py-0.5 text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500">
                              📍 {r.shelf_zone}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{r.description}</p>

                        {r.trigger_pattern && (
                          <div className="mt-2 flex items-center gap-2">
                            <span className="text-xs text-slate-400">Triggered by:</span>
                            <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-xs text-slate-500">{r.trigger_pattern}</span>
                          </div>
                        )}
                      </div>

                      {/* Affected count */}
                      <div className="shrink-0 text-center">
                        <div className="flex items-center gap-1 text-slate-500">
                          <Users className="h-4 w-4" />
                          <span className="font-bold text-slate-900 dark:text-white text-lg">{r.affected_customers}</span>
                        </div>
                        <p className="text-[10px] text-slate-400">customers</p>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      <div className="flex gap-3 mt-6">
        <Button className="flex-1" onClick={() => navigate("/reports")}>
          View Full Report <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </DashboardLayout>
  );
}
