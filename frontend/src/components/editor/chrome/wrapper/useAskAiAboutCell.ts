/* Copyright 2026 Marimo. All rights reserved. */

import { useSetAtom, useStore } from "jotai";
import useEvent from "react-use-event-hook";
import { useAIConfigActions } from "@/core/ai/config";
import { CellContextProvider } from "@/core/ai/context/providers/cell";
import { pendingAiPromptAtom } from "@/core/ai/state";
import type { CellId } from "@/core/cells/ids";
import { aiAtom } from "@/core/config/config";
import { Logger } from "@/utils/Logger";
import { useChromeActions } from "../state";
import { useAiPanelTab } from "./useAiPanel";

export function useAskAiAboutCell() {
  const store = useStore();
  const { openApplication } = useChromeActions();
  const { setAiPanelTab } = useAiPanelTab();
  const { saveModeChange } = useAIConfigActions();
  const setPendingPrompt = useSetAtom(pendingAiPromptAtom);

  return useEvent(async (cellId: CellId) => {
    const mode = store.get(aiAtom)?.mode;
    if (mode !== "agent" && mode !== "code_mode") {
      await saveModeChange("agent").catch(() =>
        Logger.error("Failed to save mode change"),
      );
    }
    setPendingPrompt({
      prompt: `@${new CellContextProvider(store).asURI(cellId)} `,
      submit: false,
      append: true,
    });
    setAiPanelTab("chat");
    openApplication("ai");
  });
}
