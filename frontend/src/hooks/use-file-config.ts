"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getDirectConfig,
  setDirectConfig,
  clearDirectConfig,
  refreshDirectFile,
  applyDirectFile,
} from "@/lib/api/files";
import type { DirectConfig } from "@/types/api";

export function useFileConfig() {
  const [config, setConfig] = useState<DirectConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setError(null);
      const data = await getDirectConfig();
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const configure = useCallback(
    async (filePath: string) => {
      setError(null);
      try {
        const result = await setDirectConfig(filePath);
        await fetchConfig();
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Configuration failed";
        setError(message);
        throw err;
      }
    },
    [fetchConfig]
  );

  const clear = useCallback(async () => {
    try {
      await clearDirectConfig();
      setConfig({ configured: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to clear config";
      setError(message);
      throw err;
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const result = await refreshDirectFile();
      await fetchConfig();
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to refresh";
      setError(message);
      throw err;
    }
  }, [fetchConfig]);

  const apply = useCallback(async () => {
    try {
      return await applyDirectFile();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to apply";
      setError(message);
      throw err;
    }
  }, []);

  return {
    config,
    loading,
    error,
    configure,
    clear,
    refresh,
    apply,
    refetch: fetchConfig,
  };
}
