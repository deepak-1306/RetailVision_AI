import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Video as VideoIcon,
  VideoOff,
  Radio,
  Users,
  Gauge,
  Cpu,
  AlertTriangle,
  Loader2,
  Camera,
  Settings2,
  Volume2,
  VolumeX,
  Grid3x3,
  Pause,
  Play,
  RefreshCw,
  Activity,
  Sparkles,
} from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { getLiveStreamStatus, liveStreamWsUrl } from "@/lib/api";
import { cn, formatBehaviourLabel } from "@/lib/utils";
import type { LiveDetectionFrame, LiveEvent, LiveStreamStatus, LiveTrack } from "@/types";

const BEHAVIOUR_COLORS: Record<string, string> = {
  viewing: "#6366f1",
  touching: "#06b6d4",
  picking: "#22c55e",
  picking_and_returning: "#f59e0b",
  picking_and_putting_back: "#f59e0b",
  no_interest_in_buying: "#64748b",
  turning_towards_shelf: "#a855f7",
  analyzing: "#94a3b8",
};

function behaviourColor(behaviour: string): string {
  return BEHAVIOUR_COLORS[behaviour] || "#6366f1";
}

type ConnectionState = "idle" | "connecting" | "streaming" | "paused" | "error" | "closed";

interface FeedEvent extends LiveEvent {
  id: string;
  receivedAt: number;
}

// Tiny two-tone chime via the Web Audio API -- no audio asset needed.
function playChime() {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new AudioCtx();
    [880, 1320].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + i * 0.09);
      gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + i * 0.09 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.09 + 0.22);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.09);
      osc.stop(ctx.currentTime + i * 0.09 + 0.24);
    });
    setTimeout(() => ctx.close(), 500);
  } catch {
    /* no-op if the browser blocks audio before a user gesture */
  }
}

export default function LiveStreamPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement>(document.createElement("canvas"));
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureLoopRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const pausedRef = useRef(false);

  const [engineStatus, setEngineStatus] = useState<LiveStreamStatus | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [liveFrame, setLiveFrame] = useState<LiveDetectionFrame | null>(null);
  const [wsFps, setWsFps] = useState(0);
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [showZones, setShowZones] = useState(true);
  const [soundOn, setSoundOn] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [snapshotFlash, setSnapshotFlash] = useState(false);

  useEffect(() => {
    getLiveStreamStatus().then(setEngineStatus).catch(() => setEngineStatus(null));
  }, []);

  // ------------------------------------------------------------- overlay draw
  const drawOverlay = useCallback(
    (frame: LiveDetectionFrame | null) => {
      const canvas = overlayRef.current;
      const video = videoRef.current;
      if (!canvas || !video) return;

      const cw = video.clientWidth;
      const ch = video.clientHeight;
      if (canvas.width !== cw || canvas.height !== ch) {
        canvas.width = cw;
        canvas.height = ch;
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!frame || frame.frame_width === 0) return;

      const scaleX = cw / frame.frame_width;
      const scaleY = ch / frame.frame_height;

      if (showZones) {
        frame.shelf_zones.forEach((zone, i) => {
          const zx = zone.x1 * cw;
          const zy = zone.y1 * ch;
          const zw = (zone.x2 - zone.x1) * cw;
          const zh = (zone.y2 - zone.y1) * ch;
          ctx.strokeStyle = "rgba(148, 163, 184, 0.35)";
          ctx.setLineDash([6, 6]);
          ctx.lineWidth = 1.5;
          ctx.strokeRect(zx, zy, zw, zh);
          ctx.setLineDash([]);
          ctx.fillStyle = "rgba(148, 163, 184, 0.7)";
          ctx.font = "600 10px Inter, sans-serif";
          ctx.fillText(zone.name, zx + 6, zy + 14);
        });
      }

      frame.tracks.forEach((track: LiveTrack) => {
        const [x1, y1, x2, y2] = track.bbox;
        const bx = x1 * scaleX;
        const by = y1 * scaleY;
        const bw = (x2 - x1) * scaleX;
        const bh = (y2 - y1) * scaleY;
        const color = behaviourColor(track.behaviour_type);

        ctx.lineWidth = 2.5;
        ctx.strokeStyle = color;
        ctx.shadowColor = color;
        ctx.shadowBlur = 6;
        ctx.strokeRect(bx, by, bw, bh);
        ctx.shadowBlur = 0;

        // corner accents for a more "AI HUD" feel
        const cl = 12;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(bx, by + cl); ctx.lineTo(bx, by); ctx.lineTo(bx + cl, by);
        ctx.moveTo(bx + bw - cl, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cl);
        ctx.stroke();

        const label = `#${track.track_id} · ${formatBehaviourLabel(track.behaviour_type)}`;
        const sub = `Video Swin ${Math.round(track.behaviour_confidence * 100)}% · ${track.shelf_zone}`;
        ctx.font = "600 12px Inter, sans-serif";
        const labelWidth = Math.max(ctx.measureText(label).width, ctx.measureText(sub).width) + 12;

        ctx.fillStyle = color;
        ctx.fillRect(bx, Math.max(by - 34, 0), labelWidth, 34);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, bx + 6, Math.max(by - 20, 14));
        ctx.font = "500 10px Inter, sans-serif";
        ctx.fillText(sub, bx + 6, Math.max(by - 7, 27));
      });
    },
    [showZones]
  );

  useEffect(() => {
    drawOverlay(liveFrame);
  }, [liveFrame, drawOverlay]);

  // -------------------------------------------------------------- controls
  const stopCaptureLoop = () => {
    if (captureLoopRef.current !== null) {
      window.clearInterval(captureLoopRef.current);
      captureLoopRef.current = null;
    }
  };

  const stopStream = useCallback(() => {
    stopCaptureLoop();
    socketRef.current?.close();
    socketRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setConnectionState("closed");
    setLiveFrame(null);
    pausedRef.current = false;
    drawOverlay(null);
  }, [drawOverlay]);

  const openCamera = useCallback(async (mode: "environment" | "user") => {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: mode },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }
  }, []);

  const startStream = useCallback(async () => {
    setErrorMessage(null);
    setConnectionState("connecting");
    setFeed([]);

    try {
      await openCamera(facingMode);

      const ws = new WebSocket(liveStreamWsUrl("Live Camera 1"));
      socketRef.current = ws;

      let framesThisSecond = 0;
      let fpsWindowStart = performance.now();

      ws.onopen = () => setConnectionState("streaming");

      ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.type === "detections") {
          const frame = data as LiveDetectionFrame;
          setLiveFrame(frame);
          inFlightRef.current = false;
          framesThisSecond += 1;
          const now = performance.now();
          if (now - fpsWindowStart >= 1000) {
            setWsFps(framesThisSecond);
            framesThisSecond = 0;
            fpsWindowStart = now;
          }
          if (frame.events?.length) {
            const stamped: FeedEvent[] = frame.events.map((e) => ({
              ...e,
              id: `${e.track_id}-${e.timestamp}-${Math.random().toString(36).slice(2, 7)}`,
              receivedAt: Date.now(),
            }));
            setFeed((prev) => [...stamped, ...prev].slice(0, 30));
            if (soundOn && stamped.some((e) => e.behaviour_type === "picking")) {
              playChime();
            }
          }
        } else if (data.type === "error") {
          inFlightRef.current = false;
        }
      };

      ws.onerror = () => {
        setErrorMessage("Live stream connection failed. Check your network settings / backend status.");
        setConnectionState("error");
      };

      ws.onclose = () => {
        setConnectionState((prev) => (prev === "streaming" || prev === "connecting" || prev === "paused" ? "closed" : prev));
        stopCaptureLoop();
      };

      const targetFps = engineStatus?.target_fps || 8;
      const intervalMs = Math.max(1000 / targetFps, 60);
      const maxWidth = engineStatus?.max_stream_width || 960;

      captureLoopRef.current = window.setInterval(() => {
        if (pausedRef.current) return;
        const video = videoRef.current;
        if (!video || video.readyState < 2) return;
        if (ws.readyState !== WebSocket.OPEN) return;
        if (inFlightRef.current) return; // backpressure: skip frame if server hasn't replied yet

        const canvas = captureCanvasRef.current;
        const scale = Math.min(1, maxWidth / video.videoWidth);
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(
          (blob) => {
            if (blob && ws.readyState === WebSocket.OPEN) {
              inFlightRef.current = true;
              blob.arrayBuffer().then((buf) => ws.send(buf));
            }
          },
          "image/jpeg",
          0.7
        );
      }, intervalMs);
    } catch (err: any) {
      setErrorMessage(
        err?.name === "NotAllowedError"
          ? "Camera access was denied. Allow camera permissions to start the live feed."
          : err?.message || "Could not start the live stream."
      );
      setConnectionState("error");
      stopStream();
    }
  }, [engineStatus, facingMode, openCamera, soundOn, stopStream]);

  const togglePause = () => {
    pausedRef.current = !pausedRef.current;
    setConnectionState(pausedRef.current ? "paused" : "streaming");
  };

  const switchCamera = async () => {
    const next = facingMode === "environment" ? "user" : "environment";
    setFacingMode(next);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      await openCamera(next);
    }
  };

  const takeSnapshot = () => {
    const video = videoRef.current;
    const overlay = overlayRef.current;
    if (!video || !overlay) return;
    const out = document.createElement("canvas");
    out.width = overlay.width;
    out.height = overlay.height;
    const ctx = out.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, out.width, out.height);
    ctx.drawImage(overlay, 0, 0);
    const link = document.createElement("a");
    link.download = `retailvision-live-${Date.now()}.png`;
    link.href = out.toDataURL("image/png");
    link.click();
    setSnapshotFlash(true);
    setTimeout(() => setSnapshotFlash(false), 250);
  };

  const resetTracking = () => {
    socketRef.current?.send(JSON.stringify({ type: "reset" }));
    setFeed([]);
  };

  useEffect(() => stopStream, [stopStream]);

  const isStreaming = connectionState === "streaming";
  const isPaused = connectionState === "paused";
  const isActive = isStreaming || isPaused;
  const behaviourEntries = liveFrame ? Object.entries(liveFrame.behaviour_counts) : [];
  const sessionSeconds = liveFrame?.elapsed_seconds ?? 0;
  const sessionLabel = useMemo(() => {
    const m = Math.floor(sessionSeconds / 60);
    const s = Math.floor(sessionSeconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }, [sessionSeconds]);

  return (
    <DashboardLayout title="Live Stream">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-2 overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-2">
            <CardTitle className="flex items-center gap-2">
              <Radio className={cn("h-4 w-4", isStreaming && "text-rose-500 animate-pulse")} />
              Live Camera Feed
            </CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <StatusPill state={connectionState} />
              {isActive && (
                <>
                  <IconToggle title={isPaused ? "Resume" : "Pause"} onClick={togglePause}>
                    {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                  </IconToggle>
                  <IconToggle title="Switch camera" onClick={switchCamera}>
                    <RefreshCw className="h-4 w-4" />
                  </IconToggle>
                  <IconToggle title="Snapshot" onClick={takeSnapshot}>
                    <Camera className="h-4 w-4" />
                  </IconToggle>
                  <IconToggle title="Reset tracking" onClick={resetTracking}>
                    <Sparkles className="h-4 w-4" />
                  </IconToggle>
                </>
              )}
              <IconToggle title="Toggle sound alerts" active={soundOn} onClick={() => setSoundOn((v) => !v)}>
                {soundOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
              </IconToggle>
              <IconToggle title="Toggle shelf zones" active={showZones} onClick={() => setShowZones((v) => !v)}>
                <Grid3x3 className="h-4 w-4" />
              </IconToggle>
              <IconToggle title="Settings" active={showSettings} onClick={() => setShowSettings((v) => !v)}>
                <Settings2 className="h-4 w-4" />
              </IconToggle>

              {isActive ? (
                <Button size="sm" variant="danger" onClick={stopStream}>
                  <VideoOff className="h-4 w-4" /> Stop
                </Button>
              ) : (
                <Button size="sm" onClick={startStream} disabled={connectionState === "connecting"}>
                  {connectionState === "connecting" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <VideoIcon className="h-4 w-4" />
                  )}
                  Start Live Detection
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {errorMessage && (
              <div className="mb-4 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-500">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                {errorMessage}
              </div>
            )}

            <AnimatePresence>
              {showSettings && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="mb-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 px-4 py-3 text-sm space-y-1">
                    <p className="text-slate-500">
                      Target inference rate:{" "}
                      <span className="font-medium text-slate-700 dark:text-slate-200">
                        {engineStatus?.target_fps ?? 8} fps
                      </span>{" "}
                      · Stream downscaled to{" "}
                      <span className="font-medium text-slate-700 dark:text-slate-200">
                        {engineStatus?.max_stream_width ?? 960}px
                      </span>{" "}
                      wide before inference (configurable via <code>LIVE_STREAM_TARGET_FPS</code> /{" "}
                      <code>LIVE_STREAM_MAX_WIDTH</code> in the backend .env).
                    </p>
                    <p className="text-slate-400 text-xs">
                      Frames are only sent once the previous frame's detections have been received, so slower
                      devices automatically back off instead of queuing up latency.
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-slate-950 border border-slate-200 dark:border-slate-800">
              <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full object-contain" />
              <canvas ref={overlayRef} className="absolute inset-0 h-full w-full pointer-events-none" />

              {snapshotFlash && <div className="absolute inset-0 bg-white/80 pointer-events-none" />}

              {!streamRef.current && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-500">
                  <VideoIcon className="h-10 w-10 opacity-40" />
                  <p className="text-sm">Start the live feed to see boxes &amp; behaviour labels in real time</p>
                </div>
              )}
              {isPaused && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                  <Badge className="bg-white/90 text-slate-900 text-sm px-3 py-1">Paused</Badge>
                </div>
              )}
              {isStreaming && (
                <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
                  <span className="h-1.5 w-1.5 rounded-full bg-rose-500 animate-pulse" /> LIVE · {sessionLabel}
                </div>
              )}
              {liveFrame && (
                <div className="absolute top-3 right-3 flex gap-2 text-xs font-medium text-white">
                  <span className="rounded-full bg-black/60 px-2.5 py-1 backdrop-blur">
                    {liveFrame.processing_fps.toFixed(1)} infer fps
                  </span>
                  <span className="rounded-full bg-black/60 px-2.5 py-1 backdrop-blur">{wsFps} ws fps</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Cpu className="h-4 w-4" /> AI Engine</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <InfoRow label="Detector" value={engineStatus?.detector ?? "—"} />
              <InfoRow label="Tracker" value={engineStatus?.tracker ?? "—"} />
              <InfoRow label="Behaviour engine" value={engineStatus?.behaviour_engine ?? "—"} />
              <div className="pt-2 border-t border-slate-200 dark:border-slate-800">
                <Badge
                  className={
                    engineStatus?.video_swin_active
                      ? "bg-emerald-500/10 text-emerald-500"
                      : "bg-amber-500/10 text-amber-500"
                  }
                >
                  {engineStatus?.video_swin_active
                    ? "Video Swin Transformer checkpoint active"
                    : "Video Swin heuristic fallback active"}
                </Badge>
                <p className="mt-2 text-xs text-slate-400">{engineStatus?.video_swin_note}</p>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardContent className="pt-5">
                <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wide mb-1">
                  <Users className="h-3.5 w-3.5" /> In Frame
                </div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {liveFrame?.person_count ?? 0}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-5">
                <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wide mb-1">
                  <Activity className="h-3.5 w-3.5" /> Total Visitors
                </div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {liveFrame?.total_unique_visitors ?? 0}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Gauge className="h-4 w-4" /> Live Behaviour Mix</CardTitle>
            </CardHeader>
            <CardContent>
              {behaviourEntries.length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center">No customers detected yet.</p>
              ) : (
                <div className="space-y-2">
                  {behaviourEntries.map(([behaviour, count]) => (
                    <div key={behaviour} className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: behaviourColor(behaviour) }}
                        />
                        {formatBehaviourLabel(behaviour)}
                      </span>
                      <span className="font-semibold text-slate-700 dark:text-slate-200">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">Live Activity Feed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-64 overflow-y-auto scrollbar-thin space-y-2">
                <AnimatePresence initial={false}>
                  {feed.length === 0 ? (
                    <p className="text-sm text-slate-400 py-6 text-center">
                      Notable behaviours (picking, touching, returns) will appear here as they happen.
                    </p>
                  ) : (
                    feed.map((e) => (
                      <motion.div
                        key={e.id}
                        initial={{ opacity: 0, x: 12 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center gap-2 rounded-lg border border-slate-100 dark:border-slate-800 px-3 py-2 text-xs"
                      >
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: behaviourColor(e.behaviour_type) }}
                        />
                        <span className="flex-1 text-slate-600 dark:text-slate-300">
                          Customer <strong>#{e.track_id}</strong> started{" "}
                          <strong>{formatBehaviourLabel(e.behaviour_type).toLowerCase()}</strong> in{" "}
                          {e.shelf_zone}
                        </span>
                        <span className="text-slate-400 shrink-0">{e.timestamp.toFixed(1)}s</span>
                      </motion.div>
                    ))
                  )}
                </AnimatePresence>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {liveFrame && liveFrame.tracks.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mt-6">
            <CardHeader><CardTitle>Active Tracks</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-slate-500">
                    <tr>
                      <th className="py-2 pr-4">Track ID</th>
                      <th className="py-2 pr-4">Behaviour (Video Swin)</th>
                      <th className="py-2 pr-4">Confidence</th>
                      <th className="py-2 pr-4">Shelf Zone</th>
                    </tr>
                  </thead>
                  <tbody>
                    {liveFrame.tracks.map((t) => (
                      <tr key={t.track_id} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="py-2 pr-4 font-medium">#{t.track_id}</td>
                        <td className="py-2 pr-4">
                          <span
                            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
                            style={{
                              backgroundColor: `${behaviourColor(t.behaviour_type)}1a`,
                              color: behaviourColor(t.behaviour_type),
                            }}
                          >
                            {formatBehaviourLabel(t.behaviour_type)}
                          </span>
                        </td>
                        <td className="py-2 pr-4">{Math.round(t.behaviour_confidence * 100)}%</td>
                        <td className="py-2 pr-4 text-slate-500">{t.shelf_zone}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </DashboardLayout>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-slate-700 dark:text-slate-200">{value}</span>
    </div>
  );
}

function IconToggle({
  children,
  title,
  active,
  onClick,
}: {
  children: React.ReactNode;
  title: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center h-8 w-8 rounded-lg border transition-colors",
        active
          ? "border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400"
          : "border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
      )}
    >
      {children}
    </button>
  );
}

function StatusPill({ state }: { state: ConnectionState }) {
  const map: Record<ConnectionState, { label: string; className: string }> = {
    idle: { label: "Idle", className: "bg-slate-500/10 text-slate-400" },
    connecting: { label: "Connecting…", className: "bg-amber-500/10 text-amber-500" },
    streaming: { label: "Streaming", className: "bg-emerald-500/10 text-emerald-500" },
    paused: { label: "Paused", className: "bg-amber-500/10 text-amber-500" },
    error: { label: "Error", className: "bg-rose-500/10 text-rose-500" },
    closed: { label: "Stopped", className: "bg-slate-500/10 text-slate-400" },
  };
  const { label, className } = map[state];
  return <Badge className={className}>{label}</Badge>;
}
