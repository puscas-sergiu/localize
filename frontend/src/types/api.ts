// Translation state values matching backend
export type TranslationState =
  | "new"
  | "translated"
  | "needs_review"
  | "reviewed"
  | "flagged"
  | "stale"
  | "not_translated";

// Coverage statistics per language
export interface LanguageCoverage {
  translated: number;
  total: number;
  percentage: number;
}

// File statistics
export interface FileStats {
  total_strings: number;
  translatable_strings: number;
  source_language: string;
  languages: string[];
  coverage: Record<string, LanguageCoverage>;
}

// Translation entry for review
export interface Translation {
  key: string;
  source: string;
  translation: string;
  state: TranslationState;
}

// Direct file configuration
export interface DirectConfig {
  configured: boolean;
  file_path?: string;
  file_id?: string;
  configured_at?: string;
  last_synced?: string;
  file_name?: string;
  file_exists?: boolean;
  last_modified?: string;
  size_bytes?: number;
}

// Review suggestion from LLM
export interface ReviewSuggestion {
  text: string;
  explanation: string;
}

// Single translation review response
export interface ReviewSingleResponse {
  key: string;
  issues: string[];
  suggestions: ReviewSuggestion[];
  original_translation: string;
}

// Verification issue
export interface VerificationIssue {
  key: string;
  source: string;
  translation: string;
  issues: string[];
  suggested_fix?: string;
}

// File metadata
export interface FileMetadata {
  file_id: string;
  original_name: string;
  upload_time: string;
  size_bytes: number;
}

// Tab counts for navigation
export interface TabCounts {
  untranslated: number;
  needs_review: number;
  flagged: number;
  total: number;
}
