import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play, Pause, SkipBack, SkipForward, ChevronRight,
  Eye, ShoppingCart, Hand, RotateCcw, TrendingUp, AlertCircle,
  Film, Search, Video, Loader2, CheckCircle2, Clock, Download,
} from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  getFrameCount, frameUrl, getBehaviourTimeline, getJob,
  annotatedVideoUrl, downloadAnnotatedVideoUrl, getSecondBySecond,
} from "@/lib/api";
import { useJobStore } from "@/store/jobStore";
import { JobRequired } from "./JobRequired";
import type { BehaviourEvent, ProcessingJob, SecondBySecondEntry } from "@/types";

// ── constants ────────────────────────────────────────────────────────────────

const BEHAVIOUR_META: Record<string, { colour: string; bg: string; border: string; icon: React.ReactNode; emoji: string }> = {
  viewing:                  { colour: "#6366f1", bg: "bg-indigo-500/15",  border: "border-indigo-500/30",  icon: <Eye className="h-3.5 w-3.5" />,         emoji: "👁" },
  touching:                 { colour: "#22c55e", bg: "bg-emerald-500/15", border: "border-emerald-500/30", icon: <Hand className="h-3.5 w-3.5" />,        emoji: "✋" },
  picking:                  { colour: "#f59e0b", bg: "bg-amber-500/15",   border: "border-amber-500/30",   icon: <ShoppingCart className="h-3.5 w-3.5" />, emoji: "🛒" },
  picking_and_returning:    { colour: "#ef4444", bg: "bg-rose-500/15",    border: "border-rose-500/30",    icon: <RotateCcw className="h-3.5 w-3.5" />,    emoji: "↩️" },
  picking_and_putting_back: { colour: "#f97316", bg: "bg-orange-500/15",  border: "border-orange-500/30",  icon: <RotateCcw className="h-3.5 w-3.5" />,    emoji: "🔄" },
  turning_towards_shelf:    { colour: "#06b6d4", bg: "bg-cyan-500/15",    border: "border-cyan-500/30",    icon: <TrendingUp className="h-3.5 w-3.5" />,   emoji: "↪️" },
  no_interest_in_buying:    { colour: "#94a3b8", bg: "bg-slate-500/15",   border: "border-slate-500/30",   icon: <AlertCircle className="h-3.5 w-3.5" />,  emoji: "🚶" },
};

function formatLabel(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getColourForTrack(id: number): string {
  const palette = ["#6366f1","#22c55e","#f59e0b","#ef4444","#06b6d4","#a855f7","#ec4899","#f97316","#14b8a6","#84cc16"];
  return palette[id % palette.length];
}

type TabId = "video" | "frames";

// ── component ────────────────────────────────────────────────────────────────

export default function VideoPreviewPage() {
  const jobId = useJobStore((s) => s.selectedJobId);
  const navigate = useNavigate();

  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [totalFrames, setTotalFrames] = useState(0);
  const [fps, setFps] = useState(25);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [frameError, setFrameError] = useState(false);
  const [events, setEvents] = useState<BehaviourEvent[]>([]);
  const [secondBySecond, setSecondBySecond] = useState<SecondBySecondEntry[]>([]);
  const [activeTab, setActiveTab] = useState<TabId>("video");
  const [videoReady, setVideoReady] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [videoCurrentSec, setVideoCurrentSec] = useState(0);
  const [videoSrc, setVideoSrc] = useState<string>("");

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Resolve job details + video_id
  useEffect(() => {
    if (!jobId) { setLoading(false); return; }
    (async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
        setVideoId(j.video_id);
        try {
          const info = await getFrameCount(j.video_id);
          setTotalFrames(info.count);
          setFps(info.fps || 25);
        } catch { /* frame endpoint optional */ }
      } catch { /* ignored */ }
      finally { setLoading(false); }
    })();
  }, [jobId]);

  // Build video src fresh (include token to avoid stale auth)
  useEffect(() => {
    if (jobId) {
      setVideoSrc(annotatedVideoUrl(jobId));
      setVideoError(null);
      setVideoReady(false);
    }
  }, [jobId]);

  // Load behaviour events
  useEffect(() => {
    if (!jobId) return;
    getBehaviourTimeline(jobId).then(setEvents).catch(() => {});
    getSecondBySecond(jobId).then(setSecondBySecond).catch(() => {});
  }, [jobId]);

  // Frame-scrubber playback
  useEffect(() => {
    if (playing && totalFrames > 0) {
      const step = Math.max(1, Math.round(fps / 8));
      intervalRef.current = setInterval(() => {
        setCurrentFrame((f) => {
          const next = f + step;
          if (next >= totalFrames) { setPlaying(false); return totalFrames - 1; }
          return next;
        });
      }, 125);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [playing, totalFrames, fps]);

  // Track native video currentTime → sync second-by-second panel
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const handler = () => setVideoCurrentSec(Math.floor(el.currentTime));
    el.addEventListener("timeupdate", handler);
    return () => el.removeEventListener("timeupdate", handler);
  }, [videoReady]);

  const seek = useCallback((delta: number) => {
    setPlaying(false);
    setCurrentFrame((f) => Math.max(0, Math.min(totalFrames - 1, f + delta)));
  }, [totalFrames]);

  const currentTs = fps > 0 ? currentFrame / fps : 0;
  const activeEvents = events.filter((e) => e.start_time_seconds <= currentTs && e.end_time_seconds >= currentTs);
  const progress = totalFrames > 1 ? (currentFrame / (totalFrames - 1)) * 100 : 0;

  // Per-second actions for the annotated video tab
  const activeSecondEntry = secondBySecond.find((e) => e.second === videoCurrentSec);
  const nearbyEntries = secondBySecond.filter((e) => Math.abs(e.second - videoCurrentSec) <= 2);

  const hasAnnotatedVideo = !!job?.annotated_video_path;
  const isCompleted = job?.status === "completed";
  const isProcessing = job && !isCompleted && job.status !== "failed";
  const frameSrc = videoId ? frameUrl(videoId, currentFrame) : "";

  const downloadUrl = jobId ? downloadAnnotatedVideoUrl(jobId) : "";

  if (!jobId) {
    return <DashboardLayout title="Video Preview"><JobRequired /></DashboardLayout>;
  }

  return (
    <DashboardLayout title="Video Preview">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* ── Left: Main viewer ── */}
        <div className="xl:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 flex-wrap">
                <Film className="h-4 w-4 text-indigo-500 shrink-0" />
                Annotated Detection View
                {isCompleted && hasAnnotatedVideo && (
                  <span className="flex items-center gap-1 text-xs font-normal text-emerald-500">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Annotated MP4 ready
                  </span>
                )}
                {isProcessing && (
                  <span className="flex items-center gap-1 text-xs font-normal text-amber-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Processing… {job?.progress ?? 0}%
                  </span>
                )}
                {!loading && totalFrames > 0 && (
                  <span className="ml-auto text-xs font-normal text-slate-400">
                    {totalFrames.toLocaleString()} frames · {fps.toFixed(0)} fps
                  </span>
                )}
              </CardTitle>

              {/* Tab bar */}
              {isCompleted && (
                <div className="flex gap-1 mt-2 rounded-lg bg-slate-100 dark:bg-slate-800 p-1 w-fit">
                  {([
                    { id: "video" as TabId, icon: <Video className="h-3.5 w-3.5" />, label: "Annotated Video" },
                    { id: "frames" as TabId, icon: <Search className="h-3.5 w-3.5" />, label: "Frame Inspector" },
                  ]).map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                        activeTab === tab.id
                          ? "bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-slate-100"
                          : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                      }`}
                    >
                      {tab.icon} {tab.label}
                    </button>
                  ))}
                </div>
              )}
            </CardHeader>

            <CardContent className="space-y-4">
              {loading ? (
                <Skeleton className="w-full aspect-video rounded-xl" />
              ) : (
                <>
                  {/* ── TAB: Annotated Video (real MP4) ── */}
                  {activeTab === "video" && (
                    <>
                      {!isCompleted ? (
                        <div className="flex flex-col items-center justify-center aspect-video rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 gap-4">
                          <Loader2 className="h-12 w-12 animate-spin opacity-40" />
                          <div className="text-center">
                            <p className="text-sm font-medium">Video is being processed</p>
                            <p className="text-xs mt-1">
                              Status: <span className="capitalize">{job?.status?.replace(/_/g, " ") ?? "pending"}</span>
                              {" · "}{job?.progress ?? 0}% complete
                            </p>
                            <p className="text-xs mt-2 text-slate-500">The annotated MP4 will appear here when processing finishes.</p>
                          </div>
                        </div>
                      ) : !hasAnnotatedVideo ? (
                        <div className="flex flex-col items-center justify-center aspect-video rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 gap-3">
                          <AlertCircle className="h-12 w-12 opacity-40" />
                          <div className="text-center">
                            <p className="text-sm font-medium">Annotated video unavailable</p>
                            <p className="text-xs mt-1 text-slate-500">
                              {job?.error_message ?? "Switch to Frame Inspector to browse frames individually."}
                            </p>
                          </div>
                        </div>
                      ) : videoError ? (
                        /* Error state — show clear message + download fallback */
                        <div className="flex flex-col items-center justify-center aspect-video rounded-xl bg-slate-950 text-slate-300 gap-4">
                          <AlertCircle className="h-12 w-12 text-rose-400 opacity-80" />
                          <div className="text-center px-6">
                            <p className="text-sm font-semibold text-rose-400">Video failed to load in browser</p>
                            <p className="text-xs mt-1 text-slate-400">{videoError}</p>
                            <p className="text-xs mt-2 text-slate-500">
                              Please verify your network connection or click Retry. You can also download the annotated video below.
                            </p>
                          </div>
                          <div className="flex gap-3 flex-wrap justify-center">
                            <Button size="sm" onClick={() => { setVideoError(null); setVideoSrc(annotatedVideoUrl(jobId!) + "&nocache=" + Date.now()); }}>
                              ↺ Retry
                            </Button>
                            <a href={downloadUrl} download
                              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700 text-xs font-medium px-4 py-2 transition-colors">
                              <Download className="h-3.5 w-3.5" /> Download Video
                            </a>
                          </div>
                        </div>
                      ) : (
                        /* ── Real annotated MP4 player ── */
                        <motion.div
                          className="relative w-full aspect-video rounded-xl overflow-hidden bg-black shadow-2xl"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                        >
                          {!videoReady && (
                            <div className="absolute inset-0 z-10 flex items-center justify-center bg-black">
                              <Loader2 className="h-10 w-10 text-indigo-400 animate-spin" />
                            </div>
                          )}
                          <video
                            ref={videoRef}
                            key={videoSrc}
                            src={videoSrc}
                            className="w-full h-full object-contain"
                            controls
                            playsInline
                            preload="metadata"
                            onLoadedMetadata={() => setVideoReady(true)}
                            onError={(e) => {
                              const target = e.currentTarget;
                              const code = target.error?.code ?? "?";
                              const msg = target.error?.message || "Unknown codec or network error";
                              setVideoError(`Code ${code}: ${msg}`);
                            }}
                          />
                        </motion.div>
                      )}

                      {/* ── Second-by-second live action panel ── */}
                      {isCompleted && hasAnnotatedVideo && !videoError && secondBySecond.length > 0 && (
                        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/60 p-4">
                          <div className="flex items-center gap-2 mb-3">
                            <Clock className="h-4 w-4 text-indigo-400" />
                            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                              Actions at second {videoCurrentSec}s
                            </span>
                            {activeSecondEntry && (
                              <span className="ml-auto text-xs text-slate-400">
                                {activeSecondEntry.actions.length} active action(s)
                              </span>
                            )}
                          </div>

                          {!activeSecondEntry ? (
                            <p className="text-xs text-slate-400 py-2">
                              No detected actions at {videoCurrentSec}s — play the video to see live actions here.
                            </p>
                          ) : (
                            <div className="flex flex-wrap gap-2">
                              {activeSecondEntry.actions.map((a, i) => {
                                const m = BEHAVIOUR_META[a.behaviour_type] || BEHAVIOUR_META.viewing;
                                return (
                                  <motion.div
                                    key={i}
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${m.bg} ${m.border}`}
                                    style={{ color: m.colour }}
                                  >
                                    <span className="h-4 w-4 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0"
                                      style={{ background: getColourForTrack(a.track_id) }}>
                                      {a.track_id}
                                    </span>
                                    {m.emoji} {a.behaviour_label}
                                    <span className="opacity-60 text-[10px]">{(a.confidence * 100).toFixed(0)}%</span>
                                  </motion.div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}

                  {/* ── TAB: Frame-by-frame scrubber ── */}
                  {activeTab === "frames" && (
                    <>
                      {!videoId ? (
                        <div className="flex flex-col items-center justify-center aspect-video rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 gap-3">
                          <AlertCircle className="h-12 w-12 opacity-40" />
                          <p className="text-sm">No video found for this job.</p>
                        </div>
                      ) : (
                        <motion.div
                          className="relative w-full aspect-video rounded-xl overflow-hidden bg-black shadow-2xl"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                        >
                          <img
                            key={frameSrc}
                            src={frameSrc}
                            alt={`Frame ${currentFrame}`}
                            className="w-full h-full object-contain"
                            onError={() => setFrameError(true)}
                            onLoad={() => setFrameError(false)}
                          />
                          {frameError && (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 text-slate-300 gap-2">
                              <AlertCircle className="h-10 w-10 opacity-60" />
                              <p className="text-sm">Frame unavailable</p>
                            </div>
                          )}
                          <div className="absolute top-3 left-3 rounded-lg bg-black/70 backdrop-blur-sm text-white text-xs px-2.5 py-1.5 font-mono">
                            ⏱ {currentTs.toFixed(2)}s &nbsp;·&nbsp; frame {currentFrame}
                          </div>
                          <AnimatePresence>
                            {activeEvents.length > 0 && (
                              <motion.div
                                initial={{ opacity: 0, x: 8 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 8 }}
                                className="absolute top-3 right-3 flex flex-col gap-1.5"
                              >
                                {activeEvents.slice(0, 5).map((e) => {
                                  const m = BEHAVIOUR_META[e.behaviour_type] || BEHAVIOUR_META.viewing;
                                  return (
                                    <div
                                      key={e.id}
                                      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold backdrop-blur-sm ${m.bg} ${m.border}`}
                                      style={{ color: m.colour }}
                                    >
                                      <span className="h-4 w-4 rounded-full border flex items-center justify-center text-[9px] font-bold"
                                        style={{ borderColor: getColourForTrack(e.track_id), color: getColourForTrack(e.track_id) }}>
                                        {e.track_id}
                                      </span>
                                      {m.emoji} {formatLabel(e.behaviour_type)}
                                    </div>
                                  );
                                })}
                              </motion.div>
                            )}
                          </AnimatePresence>
                          {activeEvents.length > 0 && (
                            <div className="absolute bottom-3 left-3 rounded-lg bg-black/70 backdrop-blur-sm text-white text-xs px-2.5 py-1.5">
                              👥 {new Set(activeEvents.map(e => e.track_id)).size} person(s) detected
                            </div>
                          )}
                        </motion.div>
                      )}

                      {/* Scrubber */}
                      <div className="space-y-1.5">
                        <div className="relative w-full h-3 rounded-full bg-slate-100 dark:bg-slate-800 cursor-pointer group">
                          {totalFrames > 0 && events.map((e) => {
                            const m = BEHAVIOUR_META[e.behaviour_type] || BEHAVIOUR_META.viewing;
                            return (
                              <div
                                key={e.id}
                                className="absolute top-0 h-full opacity-50 group-hover:opacity-70 transition-opacity"
                                style={{
                                  left: `${(e.start_time_seconds / (totalFrames / fps)) * 100}%`,
                                  width: `${Math.max(((e.end_time_seconds - e.start_time_seconds) / (totalFrames / fps)) * 100, 0.5)}%`,
                                  background: m.colour,
                                  borderRadius: 2,
                                }}
                              />
                            );
                          })}
                          <div
                            className="absolute top-0 h-full w-1 bg-white shadow-lg rounded-full"
                            style={{ left: `calc(${progress}% - 2px)` }}
                          />
                          <input
                            type="range"
                            min={0}
                            max={Math.max(totalFrames - 1, 1)}
                            value={currentFrame}
                            onChange={(e) => { setPlaying(false); setCurrentFrame(Number(e.target.value)); }}
                            className="absolute inset-0 w-full opacity-0 cursor-pointer"
                          />
                        </div>
                        <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                          <span>{currentTs.toFixed(1)}s</span>
                          <span>{fps > 0 ? (totalFrames / fps).toFixed(1) : 0}s</span>
                        </div>
                      </div>

                      {/* Controls */}
                      <div className="flex items-center justify-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => { setPlaying(false); setCurrentFrame(0); }}>
                          <SkipBack className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => seek(-Math.round(fps))}>−1s</Button>
                        <Button
                          size="sm"
                          className="w-24 gap-1.5"
                          onClick={() => setPlaying((p) => !p)}
                          disabled={!videoId || totalFrames === 0}
                        >
                          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                          {playing ? "Pause" : "Play"}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => seek(Math.round(fps))}>+1s</Button>
                        <Button variant="outline" size="sm" onClick={() => { setPlaying(false); setCurrentFrame(totalFrames - 1); }}>
                          <SkipForward className="h-4 w-4" />
                        </Button>
                      </div>
                    </>
                  )}
                </>
              )}

              {/* Quick nav */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <Button className="w-full" onClick={() => navigate("/timeline")}>
                  Behaviour Timeline <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
                <Button variant="outline" className="w-full" onClick={() => navigate("/analytics")}>
                  Customer Analytics <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
                <Button variant="outline" className="w-full" onClick={() => navigate("/purchase-intent")}>
                  Purchase Intent <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
                {hasAnnotatedVideo && jobId && (
                  <a
                    href={downloadUrl}
                    download
                    className="inline-flex items-center justify-center w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 text-sm font-medium px-3 py-2 gap-1.5 transition-colors"
                  >
                    <Download className="h-4 w-4" /> Download Video
                  </a>
                )}
              </div>

            </CardContent>
          </Card>
        </div>

        {/* ── Right panel ── */}
        <div className="space-y-4">

          {/* Active at this timestamp (frame scrubber) */}
          {activeTab === "frames" && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">⚡ Live at {currentTs.toFixed(1)}s</CardTitle>
              </CardHeader>
              <CardContent>
                {activeEvents.length === 0 ? (
                  <p className="text-xs text-slate-400 py-4 text-center">No active detections at this frame</p>
                ) : (
                  <ul className="space-y-2">
                    {activeEvents.map((e) => {
                      const m = BEHAVIOUR_META[e.behaviour_type] || BEHAVIOUR_META.viewing;
                      return (
                        <motion.li
                          key={e.id}
                          layout
                          initial={{ opacity: 0, x: 6 }}
                          animate={{ opacity: 1, x: 0 }}
                          className={`flex items-center gap-2.5 rounded-xl border px-3 py-2.5 ${m.bg} ${m.border}`}
                        >
                          <div className="h-7 w-7 rounded-full flex items-center justify-center font-bold text-xs text-white shrink-0"
                            style={{ background: getColourForTrack(e.track_id) }}>
                            {e.track_id}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold" style={{ color: m.colour }}>
                              {m.emoji} {formatLabel(e.behaviour_type)}
                            </p>
                            {e.shelf_zone && <p className="text-[10px] text-slate-400">Zone: {e.shelf_zone}</p>}
                          </div>
                          <span className="text-[10px] text-slate-400">{(e.confidence * 100).toFixed(0)}%</span>
                        </motion.li>
                      );
                    })}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}

          {/* Second-by-second table (video tab) */}
          {activeTab === "video" && secondBySecond.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="h-4 w-4 text-indigo-400" />
                  Second-by-Second Actions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-[520px] overflow-y-auto space-y-1 scrollbar-thin pr-1">
                  {secondBySecond.map((entry) => {
                    const isCurrentSec = entry.second === videoCurrentSec;
                    return (
                      <div
                        key={entry.second}
                        className={`rounded-xl border px-3 py-2 transition-all ${
                          isCurrentSec
                            ? "border-indigo-500/40 bg-indigo-500/10 ring-1 ring-indigo-500/30"
                            : "border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-[10px] font-mono font-bold shrink-0 ${isCurrentSec ? "text-indigo-400" : "text-slate-400"}`}>
                            {isCurrentSec ? "▶ " : ""}{entry.second}s
                          </span>
                          <span className="text-[10px] text-slate-500">{entry.actions.length} action(s)</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {entry.actions.map((a, i) => {
                            const m = BEHAVIOUR_META[a.behaviour_type] || BEHAVIOUR_META.viewing;
                            return (
                              <span
                                key={i}
                                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${m.bg} ${m.border}`}
                                style={{ color: m.colour }}
                              >
                                <span className="h-3 w-3 rounded-full text-white flex items-center justify-center text-[7px] shrink-0"
                                  style={{ background: getColourForTrack(a.track_id) }}>{a.track_id}</span>
                                {m.emoji} {a.behaviour_label}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* All events list */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">📋 All Events ({events.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-[400px] overflow-y-auto space-y-1 scrollbar-thin pr-1">
                {events.length === 0 ? (
                  <p className="text-xs text-slate-400 py-4 text-center">
                    {isProcessing ? "Events will appear after processing completes." : "No events found."}
                  </p>
                ) : (
                  events.map((e) => {
                    const m = BEHAVIOUR_META[e.behaviour_type] || BEHAVIOUR_META.viewing;
                    const isActive = activeTab === "frames"
                      ? e.start_time_seconds <= currentTs && e.end_time_seconds >= currentTs
                      : e.start_time_seconds <= videoCurrentSec && e.end_time_seconds >= videoCurrentSec;
                    return (
                      <button
                        key={e.id}
                        onClick={() => {
                          setActiveTab("frames");
                          setPlaying(false);
                          setCurrentFrame(Math.round(e.start_time_seconds * fps));
                        }}
                        className={`w-full flex items-center gap-2 text-left rounded-xl border px-2.5 py-2 text-xs transition-all hover:opacity-90 ${
                          isActive ? `${m.bg} ${m.border} ring-1 ring-offset-0` : "border-transparent hover:bg-slate-50 dark:hover:bg-slate-800"
                        }`}
                        style={isActive ? { borderColor: m.colour } : {}}
                      >
                        <div
                          className="h-5 w-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0"
                          style={{ background: getColourForTrack(e.track_id) }}
                        >
                          {e.track_id}
                        </div>
                        <span className="font-medium truncate" style={{ color: m.colour }}>{m.emoji} {formatLabel(e.behaviour_type)}</span>
                        <span className="ml-auto text-[10px] text-slate-400 shrink-0">{e.start_time_seconds.toFixed(1)}s</span>
                      </button>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>

        </div>
      </div>
    </DashboardLayout>
  );
}
