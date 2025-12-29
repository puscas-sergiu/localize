"use client";

import { useState } from "react";
import { Sparkles, Languages, Check, Loader2 } from "lucide-react";
import { TableCell, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { STATE_COLORS, STATE_LABELS } from "@/lib/constants";
import type { Translation, TranslationState } from "@/types/api";

interface TranslationRowProps {
  translation: Translation;
  onSave: (key: string, translation: string, state: TranslationState) => Promise<void>;
  onTranslateSingle: (key: string, source: string) => Promise<void>;
  onReviewSingle: (key: string, source: string, translation: string) => void;
}

export function TranslationRow({
  translation: t,
  onSave,
  onTranslateSingle,
  onReviewSingle,
}: TranslationRowProps) {
  const [value, setValue] = useState(t.translation);
  const [saving, setSaving] = useState(false);
  const [translating, setTranslating] = useState(false);

  const isUntranslated = t.state === "not_translated" || t.state === "new" || !t.translation;
  const isReviewed = t.state === "reviewed";

  const handleBlur = async () => {
    if (value !== t.translation && value.trim() !== "") {
      setSaving(true);
      try {
        await onSave(t.key, value, "translated");
      } finally {
        setSaving(false);
      }
    }
  };

  const handleTranslate = async () => {
    setTranslating(true);
    try {
      await onTranslateSingle(t.key, t.source);
    } finally {
      setTranslating(false);
    }
  };

  const handleApprove = async () => {
    setSaving(true);
    try {
      await onSave(t.key, value || t.translation, "reviewed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <TableRow
      className={cn(
        "transition-colors border-b border-zinc-800",
        isUntranslated && "bg-amber-950/10",
        isReviewed && "bg-blue-950/10",
        t.state === "flagged" && "bg-amber-950/20"
      )}
    >
      <TableCell className="py-3 align-top">
        <code className="text-xs text-zinc-500 break-all font-mono">{t.key}</code>
      </TableCell>
      <TableCell className="py-3 align-top">
        <span className="text-sm text-zinc-400">{t.source}</span>
      </TableCell>
      <TableCell className="py-3">
        <div className="relative">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") {
                setValue(t.translation);
                e.currentTarget.blur();
              }
            }}
            placeholder={isUntranslated ? "Not translated" : ""}
            className={cn(
              "bg-zinc-800/50 border-zinc-700 text-white text-sm h-9",
              isUntranslated && "border-dashed border-amber-700/50 placeholder:text-zinc-600"
            )}
          />
          {saving && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-zinc-500" />
          )}
        </div>
      </TableCell>
      <TableCell className="py-3">
        <Badge className={cn("text-xs", STATE_COLORS[t.state] || "bg-zinc-600")}>
          {STATE_LABELS[t.state] || t.state}
        </Badge>
      </TableCell>
      <TableCell className="py-3">
        <div className="flex items-center justify-end gap-1">
          {isUntranslated ? (
            <Button
              size="icon"
              variant="ghost"
              onClick={handleTranslate}
              disabled={translating}
              title="Auto-translate"
              className="h-8 w-8 text-zinc-500 hover:text-blue-400"
            >
              {translating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Languages className="w-4 h-4" />
              )}
            </Button>
          ) : (
            <>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => onReviewSingle(t.key, t.source, t.translation)}
                title="LLM Review"
                className="h-8 w-8 text-zinc-500 hover:text-purple-400"
              >
                <Sparkles className="w-4 h-4" />
              </Button>
              {!isReviewed && (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={handleApprove}
                  disabled={saving}
                  title="Mark as reviewed"
                  className="h-8 w-8 text-zinc-500 hover:text-emerald-400"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Check className="w-4 h-4" />
                  )}
                </Button>
              )}
            </>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
