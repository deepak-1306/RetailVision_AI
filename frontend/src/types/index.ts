export interface User {
  id: string;
  email: string;
  full_name: string;
  store_name: string | null;
  is_active: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Video {
  id: string;
  filename: string;
  original_name: string;
  duration_seconds: number | null;
  fps: number | null;
  width: number | null;
  height: number | null;
  store_zone: string | null;
  uploaded_at: string;
}

export type JobStatus =
  | "pending"
  | "preprocessing"
  | "detecting"
  | "tracking"
  | "classifying_behaviour"
  | "predicting_intent"
  | "generating_recommendations"
  | "annotating_video"
  | "generating_insights"
  | "generating_report"
  | "completed"
  | "failed";

export interface ProcessingJob {
  id: string;
  video_id: string;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  annotated_video_path: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface BehaviourEvent {
  id: string;
  job_id: string;
  track_id: number;
  behaviour_type: string;
  start_time_seconds: number;
  end_time_seconds: number;
  confidence: number;
  shelf_zone: string | null;
}

export interface BehaviourDistributionItem {
  behaviour_type: string;
  count: number;
  percentage: number;
}

export interface CustomerJourneyItem {
  track_id: number;
  events: BehaviourEvent[];
  total_dwell_seconds: number;
}

export interface PurchaseIntentPrediction {
  id: string;
  job_id: string;
  track_id: number;
  dwell_time_seconds: number;
  touch_count: number;
  pick_count: number;
  return_count: number;
  viewing_duration_seconds: number;
  purchase_intent_score: number;
  intent_label: "low" | "medium" | "high";
}

export interface PurchaseIntentSummary {
  average_score: number;
  high_intent_customers: number;
  medium_intent_customers: number;
  low_intent_customers: number;
  total_customers: number;
}

export interface Recommendation {
  id: string;
  job_id: string;
  shelf_zone: string | null;
  trigger_pattern: string;
  priority: "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  affected_customers: number;
}

export interface SecondBySecondAction {
  track_id: number;
  behaviour_type: string;
  behaviour_label: string;
  confidence: number;
  shelf_zone: string;
}

export interface SecondBySecondEntry {
  second: number;
  timestamp: string;
  actions: SecondBySecondAction[];
}

// ---------- Live streaming ----------
export interface LiveStreamStatus {
  detector: string;
  tracker: string;
  behaviour_engine: string;
  video_swin_active: boolean;
  video_swin_note: string;
  max_stream_width: number;
  target_fps: number;
}

export interface LiveShelfZone {
  name: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface LiveTrack {
  track_id: number;
  bbox: [number, number, number, number];
  behaviour_type: string;
  behaviour_confidence: number;
  shelf_zone: string;
}

export interface LiveEvent {
  track_id: number;
  behaviour_type: string;
  shelf_zone: string;
  confidence: number;
  timestamp: number;
}

export interface LiveDetectionFrame {
  type: "detections";
  frame_width: number;
  frame_height: number;
  timestamp: number;
  processing_fps: number;
  person_count: number;
  total_unique_visitors: number;
  behaviour_counts: Record<string, number>;
  tracks: LiveTrack[];
  events: LiveEvent[];
  shelf_zones: LiveShelfZone[];
  engine: "video_swin_transformer" | "video_swin_transformer_heuristic_fallback";
  store_zone: string | null;
  elapsed_seconds?: number;
}

export interface ReportOut {
  id: string;
  job_id: string;
  file_path: string;
  summary: string | null;
  llm_insights: string | null;
  generated_at: string;
}
