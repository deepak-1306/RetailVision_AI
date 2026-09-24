import axios from "axios";
import type {
  BehaviourDistributionItem,
  BehaviourEvent,
  CustomerJourneyItem,
  LiveStreamStatus,
  ProcessingJob,
  PurchaseIntentPrediction,
  PurchaseIntentSummary,
  Recommendation,
  ReportOut,
  SecondBySecondEntry,
  TokenPair,
  User,
  Video,
} from "@/types";

const envBase = import.meta.env.VITE_API_BASE_URL;
const API_BASE_URL = envBase && envBase.trim().length > 0 
  ? envBase 
  : (typeof window !== "undefined" && window.location.origin && !window.location.origin.includes(":5173")
      ? `${window.location.origin}/api/v1`
      : "http://localhost:8000/api/v1");

export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("rv_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("rv_access_token");
      localStorage.removeItem("rv_refresh_token");
      localStorage.removeItem("rv_user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---------- Auth ----------
export async function registerUser(payload: {
  email: string;
  full_name: string;
  password: string;
  store_name?: string;
}): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>("/auth/register", payload);
  return data;
}

export async function loginUser(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>("/auth/login-json", { email, password });
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}

// ---------- Videos ----------
export async function uploadVideo(
  file: File,
  onProgress?: (pct: number) => void
): Promise<{ video: Video; job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/videos/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100));
    },
  });
  return data;
}

export async function listVideos(): Promise<Video[]> {
  const { data } = await api.get<Video[]>("/videos");
  return data;
}

export async function deleteVideo(videoId: string): Promise<void> {
  await api.delete(`/videos/${videoId}`);
}

// ---------- Jobs ----------
export async function getJob(jobId: string): Promise<ProcessingJob> {
  const { data } = await api.get<ProcessingJob>(`/jobs/${jobId}`);
  return data;
}

export async function listJobs(): Promise<ProcessingJob[]> {
  const { data } = await api.get<ProcessingJob[]>("/jobs");
  return data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`/jobs/${jobId}`);
}

// ---------- Behaviours ----------
export async function getBehaviourTimeline(jobId: string): Promise<BehaviourEvent[]> {
  const { data } = await api.get<BehaviourEvent[]>(`/behaviours/${jobId}/timeline`);
  return data;
}

export async function getSecondBySecond(jobId: string): Promise<SecondBySecondEntry[]> {
  const { data } = await api.get<SecondBySecondEntry[]>(`/behaviours/${jobId}/second-by-second`);
  return data;
}

export async function getBehaviourDistribution(jobId: string): Promise<BehaviourDistributionItem[]> {
  const { data } = await api.get<BehaviourDistributionItem[]>(`/behaviours/${jobId}/distribution`);
  return data;
}

export async function getCustomerJourney(jobId: string): Promise<CustomerJourneyItem[]> {
  const { data } = await api.get<CustomerJourneyItem[]>(`/behaviours/${jobId}/customer-journey`);
  return data;
}

// ---------- Predictions ----------
export async function getPredictions(jobId: string): Promise<PurchaseIntentPrediction[]> {
  const { data } = await api.get<PurchaseIntentPrediction[]>(`/predictions/${jobId}`);
  return data;
}

export async function getPredictionSummary(jobId: string): Promise<PurchaseIntentSummary> {
  const { data } = await api.get<PurchaseIntentSummary>(`/predictions/${jobId}/summary`);
  return data;
}

// ---------- Recommendations ----------
export async function getRecommendations(jobId: string): Promise<Recommendation[]> {
  const { data } = await api.get<Recommendation[]>(`/recommendations/${jobId}`);
  return data;
}

// ---------- Reports ----------
export async function getReport(jobId: string): Promise<ReportOut> {
  const { data } = await api.get<ReportOut>(`/reports/${jobId}`);
  return data;
}

export function reportDownloadUrl(jobId: string): string {
  return `${API_BASE_URL}/reports/${jobId}/download`;
}

// ---------- Live streaming ----------
export async function getLiveStreamStatus(): Promise<LiveStreamStatus> {
  const { data } = await api.get<LiveStreamStatus>("/live/status");
  return data;
}

/**
 * Builds the ws(s):// URL for the live-detection WebSocket, reusing the same
 * access token the REST client already attaches via the axios interceptor
 * above (native WebSocket can't set an Authorization header, so the token
 * travels as a query param instead -- see backend/app/api/v1/live.py).
 */
export function liveStreamWsUrl(storeZone?: string): string {
  const httpBase = API_BASE_URL.replace(/\/$/, "");
  let wsBase: string;
  if (httpBase.startsWith("http://")) {
    wsBase = httpBase.replace("http://", "ws://");
  } else if (httpBase.startsWith("https://")) {
    wsBase = httpBase.replace("https://", "wss://");
  } else if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    wsBase = `${proto}//${window.location.host}${httpBase}`;
  } else {
    wsBase = "ws://localhost:8000/api/v1";
  }
  const token = localStorage.getItem("rv_access_token") || "";
  const params = new URLSearchParams({ token });
  if (storeZone) params.set("store_zone", storeZone);
  return `${wsBase}/live/ws?${params.toString()}`;
}

// ---------- LLM Insights ----------
export async function getInsightSummary(jobId: string): Promise<{ job_id: string; summary: string }> {
  const { data } = await api.get(`/insights/${jobId}/summary`);
  return data;
}

export async function askInsight(jobId: string, question: string): Promise<{ question: string; answer: string }> {
  const { data } = await api.post("/insights/ask", { job_id: jobId, question });
  return data;
}

// ---------- Frame Preview ----------
export async function getFrameCount(
  videoId: string
): Promise<{ count: number; fps: number; video_id: string }> {
  const { data } = await api.get(`/videos/${videoId}/frame-count`);
  return data;
}

/** Returns a URL for a single annotated frame image (served as JPEG). */
export function frameUrl(videoId: string, frameIndex: number): string {
  const token = localStorage.getItem("rv_access_token") || "";
  return `${API_BASE_URL}/videos/${videoId}/frame/${frameIndex}?token=${token}`;
}

/**
 * Returns the URL to stream the fully-annotated MP4 for a completed job.
 * The browser can set this as the <video> src directly.
 */
export function annotatedVideoUrl(jobId: string): string {
  const token = localStorage.getItem("rv_access_token") || "";
  return `${API_BASE_URL}/jobs/${jobId}/annotated-video?token=${token}`;
}

export function downloadAnnotatedVideoUrl(jobId: string): string {
  const token = localStorage.getItem("rv_access_token") || "";
  return `${API_BASE_URL}/jobs/${jobId}/download-annotated-video?token=${token}`;
}

