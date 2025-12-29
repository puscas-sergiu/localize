"use client";

import { useState, useCallback, useRef } from "react";
import { createSSEConnection } from "@/lib/api/client";
import type { SSEProgressEvent, SSECompleteEvent } from "@/types/job";

interface SSEState {
  isConnected: boolean;
  progress: SSEProgressEvent | null;
  result: SSECompleteEvent["result"] | null;
  error: string | null;
}

export function useSSEProgress() {
  const [state, setState] = useState<SSEState>({
    isConnected: false,
    progress: null,
    result: null,
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(
    (
      endpoint: string,
      onComplete?: (result: SSECompleteEvent["result"]) => void
    ) => {
      // Close existing connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      setState({
        isConnected: true,
        progress: null,
        result: null,
        error: null,
      });

      eventSourceRef.current = createSSEConnection(endpoint, {
        onProgress: (data) => {
          setState((prev) => ({ ...prev, progress: data }));
        },
        onComplete: (result) => {
          setState((prev) => ({
            ...prev,
            isConnected: false,
            result: result,
          }));
          onComplete?.(result);
        },
        onError: (error) => {
          setState((prev) => ({
            ...prev,
            isConnected: false,
            error,
          }));
        },
      });
    },
    []
  );

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState((prev) => ({ ...prev, isConnected: false }));
  }, []);

  const reset = useCallback(() => {
    disconnect();
    setState({
      isConnected: false,
      progress: null,
      result: null,
      error: null,
    });
  }, [disconnect]);

  return {
    ...state,
    connect,
    disconnect,
    reset,
  };
}
