"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addLanguage } from "@/lib/api/translations";
import { AVAILABLE_LANGUAGES } from "@/lib/constants";
import { toast } from "sonner";

interface AddLanguageModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fileId: string;
  onSuccess: (language: string) => void;
}

export function AddLanguageModal({
  open,
  onOpenChange,
  fileId,
  onSuccess,
}: AddLanguageModalProps) {
  const [selectedLang, setSelectedLang] = useState<string>("");
  const [customCode, setCustomCode] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  const handleAdd = async () => {
    const langCode = selectedLang === "custom" ? customCode.trim() : selectedLang;
    if (!langCode) {
      toast.error("Please select or enter a language");
      return;
    }

    setIsAdding(true);
    try {
      await addLanguage(fileId, langCode);
      toast.success(`Added ${langCode}`);
      onSuccess(langCode);
      onOpenChange(false);
      setSelectedLang("");
      setCustomCode("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add language");
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-800 border-zinc-700 sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-white">Add Language</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <Select value={selectedLang} onValueChange={setSelectedLang}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="Select a language" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-800 border-zinc-700">
              {AVAILABLE_LANGUAGES.map((lang) => (
                <SelectItem key={lang.code} value={lang.code}>
                  {lang.name}
                </SelectItem>
              ))}
              <SelectItem value="custom">Custom code...</SelectItem>
            </SelectContent>
          </Select>

          {selectedLang === "custom" && (
            <Input
              placeholder="ISO 639-1 code (e.g., de, fr-CA)"
              value={customCode}
              onChange={(e) => setCustomCode(e.target.value)}
              className="bg-zinc-900 border-zinc-700"
            />
          )}

          <div className="flex gap-2 pt-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              className="flex-1"
              onClick={handleAdd}
              disabled={isAdding || (!selectedLang || (selectedLang === "custom" && !customCode.trim()))}
            >
              {isAdding ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Add"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
