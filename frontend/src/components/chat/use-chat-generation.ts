/* Copyright 2026 Marimo. All rights reserved. */

import type { ChatStatus } from "ai";
import { useSetAtom } from "jotai";
import { useEffect } from "react";
import { chatGenerationInProgressAtom } from "@/core/ai/state";

export function useChatGeneration(status: ChatStatus) {
  const setGenerating = useSetAtom(chatGenerationInProgressAtom);
  const isGenerating = status === "submitted" || status === "streaming";

  useEffect(() => {
    setGenerating(isGenerating);
    // useChat stops its request when the panel unmounts or becomes hidden.
    return () => setGenerating(false);
  }, [isGenerating, setGenerating]);

  return isGenerating;
}
