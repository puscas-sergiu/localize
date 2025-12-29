"use client";

import { useRouter } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { DirectFileConfig } from "@/components/settings/direct-file-config";
import { FileUpload } from "@/components/settings/file-upload";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

export default function SettingsPage() {
  const router = useRouter();

  const handleConfigured = () => {
    router.push("/");
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">Settings</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Configure your localization file
        </p>
      </div>

      <div className="space-y-6">
        {/* Active File Configuration */}
        <DirectFileConfig onConfigured={handleConfigured} />

        {/* Upload File Section (collapsed) */}
        <Collapsible>
          <CollapsibleTrigger className="flex w-full items-center justify-between bg-zinc-800/50 border border-zinc-800 rounded-lg px-4 py-3 text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
            <span>Upload File (Alternative)</span>
            <ChevronDown className="w-4 h-4" />
          </CollapsibleTrigger>
          <CollapsibleContent className="bg-zinc-800/30 border-x border-b border-zinc-800 rounded-b-lg px-4 pb-4 -mt-1">
            <FileUpload onUploaded={handleConfigured} />
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  );
}
