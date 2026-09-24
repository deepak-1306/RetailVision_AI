import React, { useEffect, useState } from "react";
import { Download, FileText, Send, Loader2 } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { askInsight, getInsightSummary, getReport, reportDownloadUrl } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import { JobRequired } from "./JobRequired";

export default function ReportsPage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const [summary, setSummary] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [qaHistory, setQaHistory] = useState<{ q: string; a: string }[]>([]);

  useEffect(() => {
    if (!jobId) { setLoading(false); return; }
    getInsightSummary(jobId)
      .then((r) => setSummary(r.summary))
      .catch(() => getReport(jobId).then((r) => setSummary(r.summary || r.llm_insights || "")).catch(() => {}))
      .finally(() => setLoading(false));
  }, [jobId]);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!jobId || !question.trim()) return;
    setAsking(true);
    try {
      const res = await askInsight(jobId, question);
      setQaHistory((prev) => [...prev, { q: res.question, a: res.answer }]);
      setQuestion("");
    } finally {
      setAsking(false);
    }
  }

  if (!jobId) {
    return <DashboardLayout title="Reports"><JobRequired /></DashboardLayout>;
  }

  const suggestions = [
    "Why are customers abandoning products?",
    "Which shelf needs optimization?",
    "What should the manager do tomorrow?",
  ];

  return (
    <DashboardLayout title="Reports">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle><FileText className="inline h-4 w-4 mr-1" /> Executive Summary</CardTitle>
              <a href={reportDownloadUrl(jobId)} target="_blank" rel="noreferrer">
                <Button size="sm" variant="outline"><Download className="h-4 w-4" /> Download PDF</Button>
              </a>
            </CardHeader>
            <CardContent>
              {loading ? <Skeleton className="h-24 w-full" /> : (
                <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{summary || "No summary generated yet."}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Ask the AI Assistant</CardTitle></CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => setQuestion(s)}
                    className="rounded-full border border-slate-200 dark:border-slate-700 px-3 py-1 text-xs text-slate-500 hover:border-brand-500 hover:text-brand-500 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>

              <div className="space-y-4 mb-4 max-h-80 overflow-y-auto scrollbar-thin">
                {qaHistory.map((qa, i) => (
                  <div key={i} className="space-y-1">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{qa.q}</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded-xl p-3">{qa.a}</p>
                  </div>
                ))}
              </div>

              <form onSubmit={handleAsk} className="flex gap-2">
                <Input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask about this session's analytics..."
                />
                <Button type="submit" disabled={asking || !question.trim()}>
                  {asking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader><CardTitle>Export</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <a href={reportDownloadUrl(jobId)} target="_blank" rel="noreferrer" className="block">
              <Button variant="outline" className="w-full"><Download className="h-4 w-4" /> Download Full PDF Report</Button>
            </a>
            <p className="text-xs text-slate-400">
              The PDF includes the executive summary, purchase intent breakdown, shelf zone stats, and all
              AI recommendations for this session.
            </p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
