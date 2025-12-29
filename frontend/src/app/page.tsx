"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Settings, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFileConfig } from "@/hooks/use-file-config";
import { getFileStats } from "@/lib/api/files";

export default function HomePage() {
  const router = useRouter();
  const { config, loading } = useFileConfig();

  useEffect(() => {
    async function redirect() {
      if (!loading && config?.configured && config.file_id) {
        try {
          const stats = await getFileStats(config.file_id);
          const languages = Object.keys(stats.coverage || {})
            .filter((lang) => lang !== stats.source_language)
            .sort();
          const firstLang = languages[0] || "de";
          router.replace(`/review/${firstLang}`);
        } catch {
          // Stats failed, but file is configured - go to first common language
          router.replace("/review/de");
        }
      }
    }
    redirect();
  }, [config, loading, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  // Not configured - show setup prompt
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
      <div className="w-16 h-16 rounded-2xl bg-zinc-800 flex items-center justify-center mb-6">
        <Settings className="w-8 h-8 text-zinc-500" />
      </div>
      <h1 className="text-xl font-semibold text-white mb-2">No File Configured</h1>
      <p className="text-zinc-500 mb-6 text-center max-w-sm text-sm">
        Configure a localization file to start reviewing and translating your strings.
      </p>
      <Button onClick={() => router.push("/settings")}>
        Go to Settings
      </Button>
    </div>
  );
}
