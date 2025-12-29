import type { SSEProgressEvent, SSECompleteEvent } from "@/types/job";

const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new ApiError(response.status, error.detail || "Request failed");
  }

  return response.json();
}

export function createSSEConnection(
  endpoint: string,
  handlers: {
    onProgress?: (data: SSEProgressEvent) => void;
    onComplete?: (data: SSECompleteEvent["result"]) => void;
    onError?: (error: string) => void;
  }
): EventSource {
  const eventSource = new EventSource(`${API_BASE}${endpoint}`);

  eventSource.addEventListener("progress", (e) => {
    const data = JSON.parse((e as MessageEvent).data);
    handlers.onProgress?.(data);
  });

  eventSource.addEventListener("complete", (e) => {
    const data = JSON.parse((e as MessageEvent).data);
    handlers.onComplete?.(data.result);
    eventSource.close();
  });

  eventSource.addEventListener("error", () => {
    handlers.onError?.("Connection error");
    eventSource.close();
  });

  return eventSource;
}
