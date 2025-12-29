"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Download, Languages, Sparkles, Search, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LanguageSidebar } from "@/components/layout/language-sidebar";
import { TabNavigation } from "@/components/dashboard/tab-navigation";
import { TranslationTable } from "@/components/dashboard/translation-table";
import { TranslateProgressModal } from "@/components/modals/translate-progress-modal";
import { LLMReviewOverlay } from "@/components/modals/llm-review-overlay";
import { AddLanguageModal } from "@/components/modals/add-language-modal";
import { ReviewSingleModal } from "@/components/modals/review-single-modal";
import { useFileConfig } from "@/hooks/use-file-config";
import { useTranslations } from "@/hooks/use-translations";
import { translateSingle, translateAllUntranslated } from "@/lib/api/translations";
import { getDownloadUrl } from "@/lib/api/files";
import { LANGUAGE_NAMES } from "@/lib/constants";
import { toast } from "sonner";
import type { TranslationState } from "@/types/api";

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const language = params.language as string;

  const { config, loading: configLoading } = useFileConfig();
  const fileId = config?.file_id || "";

  const {
    translations,
    loading,
    tabCounts,
    fetchTranslations,
    saveTranslation,
    updateLocalTranslation,
  } = useTranslations(fileId, language);

  const [activeTab, setActiveTab] = useState("untranslated");
  const [searchQuery, setSearchQuery] = useState("");
  const [translateJobId, setTranslateJobId] = useState<string | null>(null);
  const [showTranslateModal, setShowTranslateModal] = useState(false);
  const [showLLMOverlay, setShowLLMOverlay] = useState(false);
  const [showAddLanguage, setShowAddLanguage] = useState(false);
  const [reviewSingle, setReviewSingle] = useState<{
    key: string;
    source: string;
    translation: string;
  } | null>(null);

  // Load translations based on active tab
  useEffect(() => {
    if (!fileId) return;

    const stateMap: Record<string, string | undefined> = {
      untranslated: "not_translated",
      needs_review: "needs_review",
      all: undefined,
    };
    fetchTranslations(stateMap[activeTab]);
  }, [fileId, language, activeTab, fetchTranslations]);

  // Handle translate all
  const handleTranslateAll = async () => {
    try {
      const { job_id } = await translateAllUntranslated(fileId, language);
      setTranslateJobId(job_id);
      setShowTranslateModal(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start translation");
    }
  };

  // Handle single translation
  const handleTranslateSingle = useCallback(
    async (key: string, source: string) => {
      try {
        const result = await translateSingle(fileId, language, key, source);
        updateLocalTranslation(key, result.translation, result.state);
        toast.success("Translation complete");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Translation failed");
      }
    },
    [fileId, language, updateLocalTranslation]
  );

  // Handle save
  const handleSave = useCallback(
    async (key: string, translation: string, state: TranslationState) => {
      try {
        await saveTranslation(key, translation, state);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to save");
      }
    },
    [saveTranslation]
  );

  // Redirect if not configured
  if (!configLoading && !config?.configured) {
    router.replace("/settings");
    return null;
  }

  if (configLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Language Sidebar */}
      <LanguageSidebar
        fileId={fileId}
        currentLanguage={language}
        onAddLanguage={() => setShowAddLanguage(true)}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-800/30">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-medium text-white">
                {LANGUAGE_NAMES[language] || language.toUpperCase()}
              </h1>
              <p className="text-xs text-zinc-500 mt-0.5">
                Review and edit translations
              </p>
            </div>

            <div className="flex items-center gap-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder="Search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 w-56 h-9 bg-zinc-800 border-zinc-700 text-sm placeholder:text-zinc-600"
                />
              </div>

              {/* Download */}
              <Button variant="secondary" size="sm" asChild>
                <a href={getDownloadUrl(fileId)} download>
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </a>
              </Button>
            </div>
          </div>
        </div>

        {/* Tab Navigation + Actions */}
        <div className="bg-zinc-800/50 border-b border-zinc-800 px-6 flex items-center justify-between">
          <TabNavigation
            activeTab={activeTab}
            onTabChange={setActiveTab}
            counts={tabCounts}
          />

          <div className="flex items-center gap-2 py-2">
            {activeTab === "untranslated" && tabCounts.untranslated > 0 && (
              <Button size="sm" onClick={handleTranslateAll}>
                <Languages className="w-4 h-4 mr-2" />
                Translate All
              </Button>
            )}
            {activeTab === "needs_review" && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowLLMOverlay(true)}
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Run LLM Check
              </Button>
            )}
          </div>
        </div>

        {/* Count */}
        <div className="px-6 py-2 border-b border-zinc-800 flex justify-between items-center">
          <span className="text-xs text-zinc-600">
            {translations.length} strings
          </span>
          {loading && (
            <Loader2 className="w-4 h-4 animate-spin text-zinc-600" />
          )}
        </div>

        {/* Translation Table */}
        <TranslationTable
          translations={translations}
          language={language}
          searchQuery={searchQuery}
          onSave={handleSave}
          onTranslateSingle={handleTranslateSingle}
          onReviewSingle={(key, source, translation) =>
            setReviewSingle({ key, source, translation })
          }
        />
      </div>

      {/* Modals */}
      <TranslateProgressModal
        open={showTranslateModal}
        onOpenChange={setShowTranslateModal}
        jobId={translateJobId}
        language={language}
        onComplete={() => {
          const stateMap: Record<string, string | undefined> = {
            untranslated: "not_translated",
            needs_review: "needs_review",
            all: undefined,
          };
          fetchTranslations(stateMap[activeTab]);
        }}
      />

      <LLMReviewOverlay
        open={showLLMOverlay}
        onClose={() => setShowLLMOverlay(false)}
        fileId={fileId}
        language={language}
        onRefresh={() => {
          const stateMap: Record<string, string | undefined> = {
            untranslated: "not_translated",
            needs_review: "needs_review",
            all: undefined,
          };
          fetchTranslations(stateMap[activeTab]);
        }}
      />

      <AddLanguageModal
        open={showAddLanguage}
        onOpenChange={setShowAddLanguage}
        fileId={fileId}
        onSuccess={(lang) => {
          router.push(`/review/${lang}`);
        }}
      />

      {reviewSingle && (
        <ReviewSingleModal
          open={!!reviewSingle}
          onOpenChange={() => setReviewSingle(null)}
          fileId={fileId}
          language={language}
          translationKey={reviewSingle.key}
          source={reviewSingle.source}
          translation={reviewSingle.translation}
          onApply={(newTranslation) => {
            handleSave(reviewSingle.key, newTranslation, "reviewed");
            setReviewSingle(null);
          }}
        />
      )}
    </div>
  );
}
