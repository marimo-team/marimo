/* Copyright 2026 Marimo. All rights reserved. */

import type { ChatStatus } from "ai";
import { useSetAtom } from "jotai";
import { useEffect } from "react";
import { chatGenerationInProgressAtom } from "@/core/ai/state";

export function isChatBusy(status: ChatStatus): boolean {
  return status === "submitted" || status === "streaming";
}

export function useChatGeneration(isGenerating: boolean) {
  const setGenerating = useSetAtom(chatGenerationInProgressAtom);

  useEffect(() => {
    setGenerating(isGenerating);
    // useChat stops its request when the panel unmounts or becomes hidden.
    return () => setGenerating(false);
  }, [isGenerating, setGenerating]);
}
