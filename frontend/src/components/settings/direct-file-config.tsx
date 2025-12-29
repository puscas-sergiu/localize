"use client";

import { useState } from "react";
import { FolderOpen, RefreshCw, Save, Trash2, Loader2, Check, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useFileConfig } from "@/hooks/use-file-config";
import { toast } from "sonner";

interface DirectFileConfigProps {
  onConfigured?: (fileId: string) => void;
}

export function DirectFileConfig({ onConfigured }: DirectFileConfigProps) {
  const { config, loading, error, configure, clear, refresh, apply } = useFileConfig();
  const [filePath, setFilePath] = useState("");
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  const handleConfigure = async () => {
    if (!filePath.trim()) return;
    setIsConfiguring(true);
    try {
      const result = await configure(filePath.trim());
      toast.success("File configured successfully");
      onConfigured?.(result.file_id);
      setFilePath("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to configure file");
    } finally {
      setIsConfiguring(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refresh();
      toast.success("File refreshed from disk");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to refresh");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleApply = async () => {
    setIsApplying(true);
    try {
      await apply();
      toast.success("Changes applied to file");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to apply changes");
    } finally {
      setIsApplying(false);
    }
  };

  const handleClear = async () => {
    try {
      await clear();
      toast.success("Configuration cleared");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to clear config");
    }
  };

  if (loading) {
    return (
      <Card className="bg-zinc-800/50 border-zinc-800">
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-zinc-800/50 border-zinc-800">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg font-medium text-white">Active File</CardTitle>
            <CardDescription className="text-zinc-500">
              Configure the .xcstrings file to work with
            </CardDescription>
          </div>
          <Badge variant={config?.configured ? "default" : "secondary"} className={config?.configured ? "bg-emerald-600" : ""}>
            {config?.configured ? "Active" : "Not Configured"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {!config?.configured ? (
          <div className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="/path/to/Localizable.xcstrings"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600"
                onKeyDown={(e) => e.key === "Enter" && handleConfigure()}
              />
              <Button onClick={handleConfigure} disabled={isConfiguring || !filePath.trim()}>
                {isConfiguring ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <FolderOpen className="w-4 h-4 mr-2" />
                )}
                Configure
              </Button>
            </div>
            {error && (
              <div className="flex items-center gap-2 text-sm text-red-400">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-700">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center flex-shrink-0">
                  <FolderOpen className="w-5 h-5 text-zinc-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {config.file_name || "Localizable.xcstrings"}
                  </p>
                  <p className="text-xs text-zinc-500 truncate mt-0.5">
                    {config.file_path}
                  </p>
                  {config.last_synced && (
                    <p className="text-xs text-zinc-600 mt-1">
                      Last synced: {new Date(config.last_synced).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {config.file_exists ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-400" />
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" onClick={handleRefresh} disabled={isRefreshing}>
                {isRefreshing ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Refresh from Disk
              </Button>
              <Button variant="default" size="sm" onClick={handleApply} disabled={isApplying}>
                {isApplying ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                Apply Changes
              </Button>
              <Button variant="ghost" size="sm" onClick={handleClear} className="text-zinc-500 hover:text-red-400">
                <Trash2 className="w-4 h-4 mr-2" />
                Clear
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
