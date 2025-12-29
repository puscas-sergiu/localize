"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Plus, AlertTriangle, List } from "lucide-react";
import type { TabCounts } from "@/types/api";

interface TabNavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  counts: TabCounts;
}

export function TabNavigation({
  activeTab,
  onTabChange,
  counts,
}: TabNavigationProps) {
  return (
    <Tabs value={activeTab} onValueChange={onTabChange}>
      <TabsList className="bg-transparent h-auto p-0 gap-0">
        <TabsTrigger
          value="untranslated"
          className="rounded-none border-b-2 border-transparent data-[state=active]:border-zinc-400 data-[state=active]:bg-transparent px-4 py-2.5 text-zinc-500 data-[state=active]:text-white"
        >
          <Plus className="w-4 h-4 mr-2" />
          Untranslated
          {counts.untranslated > 0 && (
            <Badge variant="secondary" className="ml-2 bg-zinc-700 text-zinc-300 text-xs">
              {counts.untranslated}
            </Badge>
          )}
        </TabsTrigger>

        <TabsTrigger
          value="needs_review"
          className="rounded-none border-b-2 border-transparent data-[state=active]:border-yellow-500 data-[state=active]:bg-transparent px-4 py-2.5 text-zinc-500 data-[state=active]:text-white"
        >
          <AlertTriangle className="w-4 h-4 mr-2" />
          Needs Review
          {counts.needs_review + counts.flagged > 0 && (
            <Badge variant="secondary" className="ml-2 bg-yellow-600/20 text-yellow-400 text-xs">
              {counts.needs_review + counts.flagged}
            </Badge>
          )}
        </TabsTrigger>

        <TabsTrigger
          value="all"
          className="rounded-none border-b-2 border-transparent data-[state=active]:border-zinc-500 data-[state=active]:bg-transparent px-4 py-2.5 text-zinc-500 data-[state=active]:text-white"
        >
          <List className="w-4 h-4 mr-2" />
          All Strings
          <span className="ml-2 text-zinc-600 text-xs">({counts.total})</span>
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
