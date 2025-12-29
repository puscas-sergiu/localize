import { apiRequest } from "./client";
import type { Translation, TranslationState, FileStats } from "@/types/api";

export async function getTranslations(
  fileId: string,
  language: string,
  state?: string
) {
  const params = state ? `?state=${state}` : "";
  return apiRequest<{ language: string; translations: Translation[] }>(
    `/review/${fileId}/${language}${params}`
  );
}

export async function updateTranslation(
  fileId: string,
  language: string,
  key: string,
  translation: string,
  state: TranslationState = "translated"
) {
  return apiRequest(`/review/${fileId}/${language}/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ translation, state }),
  });
}

export async function translateSingle(
  fileId: string,
  language: string,
  key: string,
  source: string
) {
  return apiRequest<{
    status: string;
    key: string;
    translation: string;
    state: TranslationState;
    quality_score: number;
    provider: string;
  }>(`/review/${fileId}/${language}/translate-single`, {
    method: "POST",
    body: JSON.stringify({ key, source }),
  });
}

export async function translateAllUntranslated(fileId: string, language: string) {
  return apiRequest<{ job_id: string }>(
    `/review/${fileId}/${language}/translate-all-untranslated`,
    { method: "POST" }
  );
}

export async function addLanguage(fileId: string, language: string) {
  return apiRequest<{ status: string; language: string; stats: FileStats }>(
    `/languages/${fileId}`,
    {
      method: "POST",
      body: JSON.stringify({ language }),
    }
  );
}
