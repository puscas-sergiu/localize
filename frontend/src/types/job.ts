import type { VerificationIssue } from "./api";

export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface JobProgress {
  current: number;
  total: number;
  percentage: number;
  message: string;
  language: string;
  lang_progress?: number;
}

export interface TranslationStats {
  total: number;
  deepl_count: number;
  gpt4_count: number;
  failed_count: number;
  green_count: number;
  yellow_count: number;
  red_count: number;
}

export interface TranslationJobResult {
  success: boolean;
  languages_processed: string[];
  stats_by_language: Record<string, TranslationStats>;
}

export interface VerificationJobResult {
  success: boolean;
  total_reviewed: number;
  passed: number;
  needs_attention: number;
  issues: VerificationIssue[];
  has_more: boolean;
  total_unreviewed: number;
  next_offset: number;
  auto_reviewed_count: number;
  skipped_unchanged: number;
}

// SSE event types
export interface SSEProgressEvent {
  current: number;
  total: number;
  percentage: number;
  message: string;
  language: string;
  lang_progress?: number;
  stats?: TranslationStats;
}

export interface SSECompleteEvent {
  complete: true;
  result: TranslationJobResult | VerificationJobResult;
}

export interface SSEErrorEvent {
  error: string;
}
