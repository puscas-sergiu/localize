"use client";

import { useState, useEffect } from "react";
import { Loader2, AlertTriangle, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { reviewSingleTranslation } from "@/lib/api/review";
import type { ReviewSingleResponse } from "@/types/api";
import { toast } from "sonner";

interface ReviewSingleModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fileId: string;
  language: string;
  translationKey: string;
  source: string;
  translation: string;
  onApply: (newTranslation: string) => void;
}

export function ReviewSingleModal({
  open,
  onOpenChange,
  fileId,
  language,
  translationKey,
  source,
  translation,
  onApply,
}: ReviewSingleModalProps) {
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<ReviewSingleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;

    async function review() {
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const data = await reviewSingleTranslation(
          fileId,
          language,
          translationKey,
          source,
          translation
        );
        setResult(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Review failed");
      } finally {
        setLoading(false);
      }
    }
    review();
  }, [open, fileId, language, translationKey, source, translation]);

  const handleApply = (text: string) => {
    onApply(text);
    toast.success("Applied suggestion");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-800 border-zinc-700 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-white">LLM Review</DialogTitle>
        </DialogHeader>

        <div className="py-2">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
            </div>
          ) : error ? (
            <div className="text-red-400 text-sm py-4">{error}</div>
          ) : result ? (
            <div className="space-y-4">
              {/* Current translation */}
              <div>
                <label className="text-xs text-zinc-500 uppercase tracking-wider">
                  Current Translation
                </label>
                <p className="mt-1 text-sm text-zinc-300 bg-zinc-900 rounded-lg p-3">
                  {result.original_translation}
                </p>
              </div>

              {/* Issues */}
              {result.issues.length > 0 ? (
                <div>
                  <label className="text-xs text-zinc-500 uppercase tracking-wider">
                    Issues Found
                  </label>
                  <div className="mt-1 space-y-2">
                    {result.issues.map((issue, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-sm text-yellow-400 bg-yellow-950/30 rounded-lg p-3"
                      >
                        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                        <span>{issue}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-emerald-400 bg-emerald-950/30 rounded-lg p-3">
                  <Check className="w-4 h-4" />
                  <span className="text-sm">No issues found</span>
                </div>
              )}

              {/* Suggestions */}
              {result.suggestions.length > 0 && (
                <div>
                  <label className="text-xs text-zinc-500 uppercase tracking-wider">
                    Suggestions
                  </label>
                  <div className="mt-1 space-y-2">
                    {result.suggestions.map((suggestion, i) => (
                      <div
                        key={i}
                        className="bg-zinc-900 rounded-lg p-3 space-y-2"
                      >
                        <p className="text-sm text-white">{suggestion.text}</p>
                        <p className="text-xs text-zinc-500">
                          {suggestion.explanation}
                        </p>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleApply(suggestion.text)}
                        >
                          Apply
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
