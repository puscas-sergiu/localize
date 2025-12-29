"use client";

import { useState, useCallback } from "react";
import { getTranslations, updateTranslation } from "@/lib/api/translations";
import type { Translation, TranslationState, TabCounts } from "@/types/api";

export function useTranslations(fileId: string, language: string) {
  const [translations, setTranslations] = useState<Translation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabCounts, setTabCounts] = useState<TabCounts>({
    untranslated: 0,
    needs_review: 0,
    flagged: 0,
    total: 0,
  });

  const calculateTabCounts = useCallback((allTranslations: Translation[]) => {
    const counts: TabCounts = {
      untranslated: 0,
      needs_review: 0,
      flagged: 0,
      total: allTranslations.length,
    };

    for (const t of allTranslations) {
      if (t.state === "not_translated" || t.state === "new" || !t.translation) {
        counts.untranslated++;
      } else if (t.state === "needs_review") {
        counts.needs_review++;
      } else if (t.state === "flagged") {
        counts.flagged++;
      }
    }

    setTabCounts(counts);
  }, []);

  const fetchTranslations = useCallback(
    async (stateFilter?: string) => {
      if (!fileId || !language) return;

      setLoading(true);
      setError(null);
      try {
        const data = await getTranslations(fileId, language, stateFilter);
        setTranslations(data.translations);

        // Calculate counts if fetching all or untranslated
        if (!stateFilter || stateFilter === "not_translated") {
          // Fetch all to calculate correct counts
          if (stateFilter) {
            const allData = await getTranslations(fileId, language);
            calculateTabCounts(allData.translations);
          } else {
            calculateTabCounts(data.translations);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    },
    [fileId, language, calculateTabCounts]
  );

  const saveTranslation = useCallback(
    async (key: string, translation: string, state: TranslationState = "translated") => {
      await updateTranslation(fileId, language, key, translation, state);
      // Update local state
      setTranslations((prev) =>
        prev.map((t) => (t.key === key ? { ...t, translation, state } : t))
      );
      // Update counts
      setTabCounts((prev) => {
        const newCounts = { ...prev };
        const oldTrans = translations.find((t) => t.key === key);
        if (oldTrans) {
          // Decrement old state count
          if (oldTrans.state === "not_translated" || oldTrans.state === "new" || !oldTrans.translation) {
            newCounts.untranslated = Math.max(0, newCounts.untranslated - 1);
          } else if (oldTrans.state === "needs_review") {
            newCounts.needs_review = Math.max(0, newCounts.needs_review - 1);
          } else if (oldTrans.state === "flagged") {
            newCounts.flagged = Math.max(0, newCounts.flagged - 1);
          }
        }
        return newCounts;
      });
    },
    [fileId, language, translations]
  );

  const updateLocalTranslation = useCallback(
    (key: string, translation: string, state: TranslationState) => {
      setTranslations((prev) =>
        prev.map((t) => (t.key === key ? { ...t, translation, state } : t))
      );
    },
    []
  );

  return {
    translations,
    loading,
    error,
    tabCounts,
    fetchTranslations,
    saveTranslation,
    updateLocalTranslation,
  };
}
