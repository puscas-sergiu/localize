"use client";

import { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useSSEProgress } from "@/hooks/use-sse-progress";
import type { TranslationJobResult } from "@/types/job";

interface TranslateProgressModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string | null;
  language: string;
  onComplete: (result: TranslationJobResult) => void;
}

export function TranslateProgressModal({
  open,
  onOpenChange,
  jobId,
  language,
  onComplete,
}: TranslateProgressModalProps) {
  const { isConnected, progress, result, error, connect, disconnect, reset } =
    useSSEProgress();

  useEffect(() => {
    if (jobId && open) {
      connect(`/translate/${jobId}/stream`, (res) => {
        onComplete(res as TranslationJobResult);
      });
    }
    return () => disconnect();
  }, [jobId, open, connect, disconnect, onComplete]);

  const handleClose = () => {
    reset();
    onOpenChange(false);
  };

  const typedResult = result as TranslationJobResult | null;
  const stats = typedResult?.stats_by_language?.[language];

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-zinc-800 border-zinc-700 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-white">Translating Strings</DialogTitle>
        </DialogHeader>

        {!typedResult ? (
          <div className="space-y-4 py-4">
            <div className="flex justify-between text-sm text-zinc-400">
              <span>{progress?.message || "Starting translation..."}</span>
              <span className="tabular-nums">{Math.round(progress?.percentage || 0)}%</span>
            </div>
            <Progress value={progress?.percentage || 0} className="h-2" />
          </div>
        ) : (
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-zinc-900 rounded-lg p-4 text-center">
                <div className="text-2xl font-semibold text-emerald-400 tabular-nums">
                  {stats?.green_count || 0}
                </div>
                <div className="text-xs text-zinc-500 mt-1">High Quality</div>
              </div>
              <div className="bg-zinc-900 rounded-lg p-4 text-center">
                <div className="text-2xl font-semibold text-yellow-400 tabular-nums">
                  {stats?.yellow_count || 0}
                </div>
                <div className="text-xs text-zinc-500 mt-1">Needs Review</div>
              </div>
            </div>
            <Button
              variant="secondary"
              className="w-full"
              onClick={handleClose}
            >
              Close
            </Button>
          </div>
        )}

        {error && (
          <div className="text-red-400 text-sm py-2">{error}</div>
        )}
      </DialogContent>
    </Dialog>
  );
}
