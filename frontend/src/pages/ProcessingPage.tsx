import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Progress } from "@/components/ui/Progress";
import { Button } from "@/components/ui/Button";
import { getJob } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import type { JobStatus } from "@/types";

const STAGES: { key: JobStatus; label: string }[] = [
  { key: "preprocessing", label: "Preprocessing video" },
  { key: "detecting", label: "YOLOv11 object detection" },
  { key: "tracking", label: "ByteTrack multi-object tracking" },
  { key: "classifying_behaviour", label: "Video Swin behaviour recognition" },
  { key: "predicting_intent", label: "XGBoost purchase intent prediction" },
  { key: "generating_recommendations", label: "Generating recommendations" },
  { key: "annotating_video", label: "Writing annotated MP4" },
  { key: "generating_insights", label: "LLM business insight generation" },
  { key: "generating_report", label: "Building PDF report" },
];

export default function ProcessingPage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const [status, setStatus] = useState<JobStatus>("pending");
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) {
      navigate("/upload");
      return;
    }

    async function poll() {
      try {
        const job = await getJob(jobId!);
        setStatus(job.status);
        setProgress(job.progress);
        if (job.status === "completed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setTimeout(() => navigate("/video-preview"), 800);
        }
        if (job.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setErrorMsg(job.error_message || "Processing failed");
        }
      } catch {
        // transient network error, keep polling
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 4000); // 4s — avoids hammering the backend
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [jobId, navigate]);

  const currentStageIndex = STAGES.findIndex((s) => s.key === status);

  return (
    <DashboardLayout title="Processing">
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>AI Pipeline in Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-6">
              <Progress value={progress} className="h-3" />
              <p className="mt-2 text-sm text-slate-500">{progress}% complete</p>
            </div>

            {errorMsg ? (
              <div className="flex items-start gap-3 rounded-xl bg-rose-500/10 p-4 text-rose-500">
                <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Processing failed</p>
                  <p className="text-sm mt-1">{errorMsg}</p>
                  <Button className="mt-3" size="sm" variant="outline" onClick={() => navigate("/upload")}>
                    Try another video
                  </Button>
                </div>
              </div>
            ) : (
              <ul className="space-y-3">
                {STAGES.map((stage, i) => {
                  const done = currentStageIndex > i || status === "completed";
                  const active = currentStageIndex === i;
                  return (
                    <motion.li
                      key={stage.key}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-center gap-3 text-sm"
                    >
                      {done ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
                      ) : active ? (
                        <Loader2 className="h-5 w-5 text-brand-500 animate-spin shrink-0" />
                      ) : (
                        <div className="h-5 w-5 rounded-full border-2 border-slate-300 dark:border-slate-700 shrink-0" />
                      )}
                      <span className={done || active ? "text-slate-800 dark:text-slate-100" : "text-slate-400"}>
                        {stage.label}
                      </span>
                    </motion.li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
