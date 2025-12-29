import { apiRequest } from "./client";
import type { FileStats, DirectConfig } from "@/types/api";

export async function uploadFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/files/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function getFileInfo(fileId: string) {
  return apiRequest<{ file_id: string; filename: string; stats: FileStats }>(
    `/files/${fileId}`
  );
}

export async function getFileStats(fileId: string) {
  return apiRequest<FileStats>(`/stats/${fileId}`);
}

export async function deleteFile(fileId: string) {
  return apiRequest(`/files/${fileId}`, { method: "DELETE" });
}

export function getDownloadUrl(fileId: string) {
  return `/api/files/${fileId}/download`;
}

// Direct file config
export async function getDirectConfig() {
  return apiRequest<DirectConfig>("/direct/config");
}

export async function setDirectConfig(filePath: string) {
  return apiRequest<{ file_id: string; file_path: string; stats: FileStats }>(
    "/direct/config",
    {
      method: "POST",
      body: JSON.stringify({ file_path: filePath }),
    }
  );
}

export async function clearDirectConfig() {
  return apiRequest("/direct/config", { method: "DELETE" });
}

export async function refreshDirectFile() {
  return apiRequest<{ status: string; stats: FileStats }>("/direct/refresh", {
    method: "POST",
  });
}

export async function applyDirectFile() {
  return apiRequest<{ status: string; message: string }>("/direct/apply", {
    method: "POST",
  });
}
