import { apiRequest } from "./client";
import type { ReviewSingleResponse } from "@/types/api";

export async function reviewSingleTranslation(
  fileId: string,
  language: string,
  key: string,
  source: string,
  translation: string
) {
  return apiRequest<ReviewSingleResponse>(
    `/review/${fileId}/${language}/review-single`,
    {
      method: "POST",
      body: JSON.stringify({ key, source, translation }),
    }
  );
}

export async function startVerification(
  fileId: string,
  language: string,
  offset = 0,
  includeReviewed = false
) {
  return apiRequest<{ job_id: string }>(`/verify/${fileId}`, {
    method: "POST",
    body: JSON.stringify({
      language,
      offset,
      include_reviewed: includeReviewed,
    }),
  });
}
