"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Play, Check, Flag, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { startVerification } from "@/lib/api/review";
import { updateTranslation } from "@/lib/api/translations";
import { useSSEProgress } from "@/hooks/use-sse-progress";
import { toast } from "sonner";
import type { VerificationJobResult } from "@/types/job";
import type { VerificationIssue } from "@/types/api";

interface LLMReviewOverlayProps {
  open: boolean;
  onClose: () => void;
  fileId: string;
  language: string;
  onRefresh: () => void;
}

type Phase = "start" | "processing" | "results";

export function LLMReviewOverlay({
  open,
  onClose,
  fileId,
  language,
  onRefresh,
}: LLMReviewOverlayProps) {
  const [phase, setPhase] = useState<Phase>("start");
  const [autoContinue, setAutoContinue] = useState(true);
  const [includeReviewed, setIncludeReviewed] = useState(false);
  const [allIssues, setAllIssues] = useState<VerificationIssue[]>([]);
  const [stats, setStats] = useState({ passed: 0, attention: 0, autoReviewed: 0 });
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [processingKeys, setProcessingKeys] = useState<Set<string>>(new Set());

  const { progress, connect, disconnect, reset } = useSSEProgress();

  const handleBatchComplete = useCallback(
    async (res: VerificationJobResult) => {
      // Accumulate results
      setAllIssues((prev) => [...prev, ...res.issues]);
      setStats((prev) => ({
        passed: prev.passed + res.passed,
        attention: prev.attention + res.needs_attention,
        autoReviewed: prev.autoReviewed + res.auto_reviewed_count,
      }));
      setNextOffset(res.next_offset);
      setHasMore(res.has_more);

      // Auto-continue or show results
      if (res.has_more && autoContinue) {
        try {
          const { job_id } = await startVerification(
            fileId,
            language,
            res.next_offset,
            includeReviewed
          );
          connect(`/verify/${job_id}/stream`, (result) =>
            handleBatchComplete(result as VerificationJobResult)
          );
        } catch {
          setPhase("results");
        }
      } else {
        setPhase("results");
      }
    },
    [autoContinue, connect, fileId, includeReviewed, language]
  );

  const startReview = async () => {
    setPhase("processing");
    setAllIssues([]);
    setStats({ passed: 0, attention: 0, autoReviewed: 0 });
    setNextOffset(0);

    try {
      const { job_id } = await startVerification(fileId, language, 0, includeReviewed);
      connect(`/verify/${job_id}/stream`, (result) =>
        handleBatchComplete(result as VerificationJobResult)
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start verification");
      setPhase("start");
    }
  };

  const applySuggestion = async (issue: VerificationIssue) => {
    if (!issue.suggested_fix) return;
    setProcessingKeys((prev) => new Set(prev).add(issue.key));
    try {
      await updateTranslation(fileId, language, issue.key, issue.suggested_fix, "reviewed");
      setAllIssues((prev) => prev.filter((i) => i.key !== issue.key));
      onRefresh();
      toast.success("Applied suggestion");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to apply");
    } finally {
      setProcessingKeys((prev) => {
        const next = new Set(prev);
        next.delete(issue.key);
        return next;
      });
    }
  };

  const dismissIssue = async (issue: VerificationIssue) => {
    setProcessingKeys((prev) => new Set(prev).add(issue.key));
    try {
      await updateTranslation(fileId, language, issue.key, issue.translation, "reviewed");
      setAllIssues((prev) => prev.filter((i) => i.key !== issue.key));
      onRefresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to dismiss");
    } finally {
      setProcessingKeys((prev) => {
        const next = new Set(prev);
        next.delete(issue.key);
        return next;
      });
    }
  };

  const flagIssue = async (issue: VerificationIssue) => {
    setProcessingKeys((prev) => new Set(prev).add(issue.key));
    try {
      await updateTranslation(fileId, language, issue.key, issue.translation, "flagged");
      setAllIssues((prev) => prev.filter((i) => i.key !== issue.key));
      onRefresh();
      toast.success("Flagged for review");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to flag");
    } finally {
      setProcessingKeys((prev) => {
        const next = new Set(prev);
        next.delete(issue.key);
        return next;
      });
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  const handleClose = () => {
    disconnect();
    reset();
    setPhase("start");
    setAllIssues([]);
    setStats({ passed: 0, attention: 0, autoReviewed: 0 });
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-zinc-900/98">
      <div className="absolute inset-4 md:inset-6 lg:inset-8 bg-zinc-800 rounded-xl border border-zinc-700 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-zinc-700 flex items-center justify-between bg-zinc-800">
          <h2 className="text-lg font-medium text-white">LLM Review</h2>
          <Button variant="ghost" size="icon" onClick={handleClose} className="text-zinc-500 hover:text-white">
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        {phase === "start" && (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="space-y-4 mb-8 w-full max-w-xs">
              <label className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Auto-continue batches</span>
                <Switch checked={autoContinue} onCheckedChange={setAutoContinue} />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Re-check reviewed strings</span>
                <Switch checked={includeReviewed} onCheckedChange={setIncludeReviewed} />
              </label>
            </div>
            <Button onClick={startReview} size="lg">
              <Play className="w-4 h-4 mr-2" />
              Start Verification
            </Button>
          </div>
        )}

        {phase === "processing" && (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="w-64 space-y-4">
              <Progress value={progress?.percentage || 0} className="h-2" />
              <p className="text-zinc-400 text-sm text-center">
                {progress?.message || "Processing..."}
              </p>
            </div>
          </div>
        )}

        {phase === "results" && (
          <>
            {/* Stats */}
            <div className="px-6 py-4 border-b border-zinc-700 grid grid-cols-3 gap-4">
              <div className="bg-zinc-900 rounded-lg p-4 text-center">
                <div className="text-2xl font-semibold text-emerald-400 tabular-nums">{stats.passed}</div>
                <div className="text-xs text-zinc-500 mt-1">Passed</div>
              </div>
              <div className="bg-zinc-900 rounded-lg p-4 text-center">
                <div className="text-2xl font-semibold text-yellow-400 tabular-nums">{stats.attention}</div>
                <div className="text-xs text-zinc-500 mt-1">Needs Attention</div>
              </div>
              <div className="bg-zinc-900 rounded-lg p-4 text-center">
                <div className="text-2xl font-semibold text-blue-400 tabular-nums">{stats.autoReviewed}</div>
                <div className="text-xs text-zinc-500 mt-1">Auto-Reviewed</div>
              </div>
            </div>

            {/* Issues Table */}
            <ScrollArea className="flex-1">
              {allIssues.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full py-16">
                  <div className="w-16 h-16 rounded-full bg-emerald-900/30 flex items-center justify-center mb-4">
                    <Check className="w-8 h-8 text-emerald-400" />
                  </div>
                  <p className="text-white text-lg font-medium">All Clear!</p>
                  <p className="text-zinc-500 text-sm mt-1">No issues found in this batch</p>
                </div>
              ) : (
                <Table>
                  <TableHeader className="bg-zinc-800 sticky top-0">
                    <TableRow className="border-b border-zinc-700">
                      <TableHead className="text-zinc-500 text-xs">Key</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Issues</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Suggestion</TableHead>
                      <TableHead className="text-zinc-500 text-xs text-right w-36">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allIssues.map((issue) => {
                      const isProcessing = processingKeys.has(issue.key);
                      return (
                        <TableRow key={issue.key} className="border-b border-zinc-800">
                          <TableCell className="py-3">
                            <code className="text-xs text-zinc-500 font-mono">{issue.key}</code>
                          </TableCell>
                          <TableCell className="py-3">
                            <span className="text-sm text-yellow-400">
                              {issue.issues.join(", ")}
                            </span>
                          </TableCell>
                          <TableCell className="py-3">
                            <span className="text-sm text-zinc-300">
                              {issue.suggested_fix || "—"}
                            </span>
                          </TableCell>
                          <TableCell className="py-3 text-right">
                            <div className="flex items-center justify-end gap-1">
                              {issue.suggested_fix && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => applySuggestion(issue)}
                                  disabled={isProcessing}
                                  className="h-8 text-emerald-400 hover:text-emerald-300"
                                >
                                  {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : "Apply"}
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => dismissIssue(issue)}
                                disabled={isProcessing}
                                className="h-8 text-zinc-500 hover:text-white"
                              >
                                Dismiss
                              </Button>
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => flagIssue(issue)}
                                disabled={isProcessing}
                                className="h-8 w-8 text-zinc-500 hover:text-amber-400"
                              >
                                <Flag className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </ScrollArea>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-zinc-700 flex justify-between">
              <Button variant="secondary" onClick={handleClose}>
                Close
              </Button>
              {hasMore && (
                <Button onClick={startReview}>
                  Continue to Next Batch
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
