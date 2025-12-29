"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getFileStats } from "@/lib/api/files";
import { cn } from "@/lib/utils";
import { LANGUAGE_NAMES, FLAG_EMOJIS } from "@/lib/constants";
import type { FileStats } from "@/types/api";

interface LanguageSidebarProps {
  fileId: string;
  currentLanguage: string;
  onAddLanguage: () => void;
}

export function LanguageSidebar({
  fileId,
  currentLanguage,
  onAddLanguage,
}: LanguageSidebarProps) {
  const [stats, setStats] = useState<FileStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!fileId) return;
      try {
        const data = await getFileStats(fileId);
        setStats(data);
      } catch (error) {
        console.error("Failed to load stats:", error);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [fileId]);

  const languages = stats?.coverage
    ? Object.keys(stats.coverage)
        .filter((lang) => lang !== stats.source_language)
        .sort()
    : [];

  if (loading) {
    return (
      <div className="w-52 bg-zinc-800/50 border-r border-zinc-800 flex-shrink-0 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="w-52 bg-zinc-800/50 border-r border-zinc-800 flex-shrink-0 flex flex-col">
      <div className="px-4 py-3 border-b border-zinc-800">
        <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
          Languages
        </h3>
      </div>

      <ScrollArea className="flex-1">
        <div className="py-1">
          {languages.map((lang) => {
            const coverage = stats?.coverage[lang];
            const isActive = lang === currentLanguage;
            const percentage = coverage?.percentage ?? 0;

            return (
              <Link
                key={lang}
                href={`/review/${lang}`}
                className={cn(
                  "flex items-center justify-between px-4 py-2.5 transition-colors border-l-2",
                  isActive
                    ? "bg-zinc-700/50 border-zinc-400 text-white"
                    : "border-transparent text-zinc-400 hover:text-white hover:bg-zinc-700/30"
                )}
              >
                <div className="flex items-center gap-2.5">
                  <span className="text-sm">{FLAG_EMOJIS[lang] || "🌐"}</span>
                  <span className="text-sm font-medium">
                    {LANGUAGE_NAMES[lang] || lang.toUpperCase()}
                  </span>
                </div>
                <div className="flex flex-col items-end">
                  <span
                    className={cn(
                      "text-xs font-medium tabular-nums",
                      percentage >= 90
                        ? "text-emerald-400"
                        : percentage >= 50
                          ? "text-yellow-400"
                          : "text-zinc-500"
                    )}
                  >
                    {Math.round(percentage)}%
                  </span>
                  <span className="text-[10px] text-zinc-600 tabular-nums">
                    {coverage?.translated}/{coverage?.total}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </ScrollArea>

      <div className="p-3 border-t border-zinc-800">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-zinc-500 hover:text-white"
          onClick={onAddLanguage}
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Language
        </Button>
      </div>
    </div>
  );
}
