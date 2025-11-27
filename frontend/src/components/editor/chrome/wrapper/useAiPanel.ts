/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

const AI_PANEL_TAB_KEY = "marimo:chrome:ai-panel-tab";

const aiPanelTabAtom = atomWithStorage<"chat" | "agents">(
  AI_PANEL_TAB_KEY,
  "chat",
  jotaiJsonStorage,
);

export function useAiPanelTab() {
  const [aiPanelTab, setAiPanelTab] = useAtom(aiPanelTabAtom);
  return { aiPanelTab, setAiPanelTab };
}
