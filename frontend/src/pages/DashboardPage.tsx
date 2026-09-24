import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Video as VideoIcon, Users, TrendingUp, Lightbulb, UploadCloud, Play, ChevronRight, Trash2, Loader2 } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { StatCard } from "@/components/StatCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { listVideos, listJobs, deleteJob } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import type { Video, ProcessingJob } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-500/10 text-emerald-500",
  failed: "bg-rose-500/10 text-rose-500",
  pending: "bg-slate-500/10 text-slate-400",
  annotating_video: "bg-indigo-500/10 text-indigo-500",
  preprocessing: "bg-blue-500/10 text-blue-400",
  detecting: "bg-violet-500/10 text-violet-400",
  classifying_behaviour: "bg-purple-500/10 text-purple-400",
  generating_insights: "bg-amber-500/10 text-amber-400",
  generating_report: "bg-orange-500/10 text-orange-400",
};

export default function DashboardPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const navigate = useNavigate();
  const { selectedJobId, setSelectedJobId } = useJobStore();

  const loadData = async () => {
    try {
      const [v, j] = await Promise.all([listVideos(), listJobs()]);
      setVideos(v);
      setJobs(j);

      // Auto-select the latest completed job if none is selected yet.
      const completed = j.filter((job) => job.status === "completed");
      if (completed.length > 0 && !selectedJobId) {
        setSelectedJobId(completed[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const completedJobs = jobs.filter((j) => j.status === "completed").length;
  const activeJobs = jobs.filter((j) => !["completed", "failed"].includes(j.status)).length;

  function openJob(jobId: string) {
    setSelectedJobId(jobId);
    navigate("/video-preview");
  }

  async function handleDeleteJob(job: ProcessingJob) {
    const video = videos.find((v) => v.id === job.video_id);
    const name = video?.original_name || "this video";
    if (!confirm(`Delete "${name}" and ALL its analytics data permanently? This cannot be undone.`)) {
      return;
    }
    setDeletingId(job.id);
    try {
      await deleteJob(job.id);
      // If the deleted job was selected, clear the selection
      if (selectedJobId === job.id) {
        const remaining = jobs.filter((j) => j.id !== job.id && j.status === "completed");
        setSelectedJobId(remaining.length > 0 ? remaining[0].id : null);
      }
      // Remove from local state immediately
      setJobs((prev) => prev.filter((j) => j.id !== job.id));
      setVideos((prev) => prev.filter((v) => v.id !== job.video_id));
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Failed to delete. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <DashboardLayout title="Dashboard">
      <div className="mb-6 flex items-center justify-between">
        <p className="text-slate-500 dark:text-slate-400">Overview of all your uploaded videos and analysis jobs.</p>
        <Button onClick={() => navigate("/upload")}>
          <UploadCloud className="h-4 w-4" /> Upload Video
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard label="Videos Uploaded" value={videos.length} icon={VideoIcon} accent="brand" />
        <StatCard label="Jobs Completed" value={completedJobs} icon={TrendingUp} accent="emerald" />
        <StatCard label="Jobs In Progress" value={activeJobs} icon={Users} accent="amber" />
        <StatCard label="Total Jobs" value={jobs.length} icon={Lightbulb} accent="rose" />
      </div>

      {/* Quick-access banner for latest completed job */}
      {!loading && completedJobs > 0 && (() => {
        const latestCompleted = jobs.find((j) => j.status === "completed");
        const vid = videos.find((v) => v.id === latestCompleted?.video_id);
        if (!latestCompleted) return null;
        return (
          <div className="mb-6 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-4 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="text-sm font-semibold text-indigo-500">✅ Latest analysis ready</p>
              <p className="text-xs text-slate-400 mt-0.5">{vid?.original_name || "Your video"}</p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button size="sm" onClick={() => openJob(latestCompleted.id)}>
                <Play className="h-3.5 w-3.5 mr-1" /> View Video
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setSelectedJobId(latestCompleted.id); navigate("/timeline"); }}>
                Timeline <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setSelectedJobId(latestCompleted.id); navigate("/analytics"); }}>
                Analytics <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setSelectedJobId(latestCompleted.id); navigate("/purchase-intent"); }}>
                Purchase Intent <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setSelectedJobId(latestCompleted.id); navigate("/recommendations"); }}>
                AI Recs <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setSelectedJobId(latestCompleted.id); navigate("/reports"); }}>
                Reports <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </div>
        );
      })()}

      <Card>
        <CardHeader>
          <CardTitle>Recent Processing Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : jobs.length === 0 ? (
            <div className="py-12 text-center text-slate-400">
              <p>No videos processed yet.</p>
              <Button className="mt-4" onClick={() => navigate("/upload")}>Upload your first video</Button>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {jobs.map((job) => {
                const video = videos.find((v) => v.id === job.video_id);
                const isSelected = job.id === selectedJobId;
                const isDeleting = deletingId === job.id;
                return (
                  <div key={job.id} className={`flex w-full items-center justify-between py-3.5 rounded-lg px-2 transition-colors ${
                      isSelected
                        ? "bg-indigo-500/10 border border-indigo-500/20"
                        : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  } ${isDeleting ? "opacity-50 pointer-events-none" : ""}`}>
                    <button
                      onClick={() => openJob(job.id)}
                      className="flex-1 text-left flex items-center justify-between pr-4"
                      disabled={isDeleting}
                    >
                      <div>
                        <p className="font-medium text-slate-800 dark:text-slate-100">
                          {isSelected && <span className="text-indigo-400 mr-1">▶</span>}
                          {video?.original_name || "Video"}
                        </p>
                        <p className="text-xs text-slate-400">{new Date(job.created_at).toLocaleString()}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-400">{job.progress}%</span>
                        <Badge className={STATUS_COLORS[job.status] || "bg-brand-500/10 text-brand-500"}>
                          {job.status.replace(/_/g, " ")}
                        </Badge>
                      </div>
                    </button>

                    {/* Delete button — always visible for every job */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20 ml-2 shrink-0"
                      disabled={isDeleting}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteJob(job);
                      }}
                      title="Delete video and all analytics data"
                    >
                      {isDeleting
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <Trash2 className="h-4 w-4" />}
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </DashboardLayout>
  );
}
