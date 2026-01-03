"use client";

import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TranslationRow } from "./translation-row";
import type { Translation, TranslationState } from "@/types/api";

interface TranslationTableProps {
  translations: Translation[];
  language: string;
  searchQuery: string;
  onSave: (key: string, translation: string, state: TranslationState) => Promise<void>;
  onTranslateSingle: (key: string, source: string) => Promise<void>;
  onReviewSingle: (key: string, source: string, translation: string) => void;
}

export function TranslationTable({
  translations,
  language,
  searchQuery,
  onSave,
  onTranslateSingle,
  onReviewSingle,
}: TranslationTableProps) {
  // Filter by search query
  const filtered = searchQuery
    ? translations.filter(
        (t) =>
          t.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.source.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.translation?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : translations;

  if (filtered.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
        {searchQuery ? "No matches found" : "No translations found"}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <Table className="table-fixed">
        <TableHeader className="bg-zinc-800/80 sticky top-0 z-10">
          <TableRow className="border-b border-zinc-700">
            <TableHead className="w-[15%] min-w-[120px] max-w-[200px] text-zinc-500 font-medium text-xs uppercase tracking-wider">Key</TableHead>
            <TableHead className="w-[20%] min-w-[150px] max-w-[250px] text-zinc-500 font-medium text-xs uppercase tracking-wider">Source (EN)</TableHead>
            <TableHead className="w-[40%] text-zinc-500 font-medium text-xs uppercase tracking-wider">Translation ({language.toUpperCase()})</TableHead>
            <TableHead className="w-20 text-zinc-500 font-medium text-xs uppercase tracking-wider">State</TableHead>
            <TableHead className="w-16 text-zinc-500 font-medium text-xs uppercase tracking-wider text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((t) => (
            <TranslationRow
              key={t.key}
              translation={t}
              onSave={onSave}
              onTranslateSingle={onTranslateSingle}
              onReviewSingle={onReviewSingle}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
