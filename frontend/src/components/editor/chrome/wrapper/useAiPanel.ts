/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

const AI_PANEL_TAB_KEY = "marimo:chrome:ai-panel-tab";

export type AiPanelTab = "chat" | "agents";

export const aiPanelTabAtom = atomWithStorage<AiPanelTab>(
  AI_PANEL_TAB_KEY,
  "chat",
  jotaiJsonStorage,
);

export function useAiPanelTab() {
  const [aiPanelTab, setAiPanelTab] = useAtom(aiPanelTabAtom);
  return { aiPanelTab, setAiPanelTab };
}
