/* Copyright 2026 Marimo. All rights reserved. */

import { useSetAtom, useStore } from "jotai";
import useEvent from "react-use-event-hook";
import { agentSessionStateAtom } from "@/components/chat/acp/state";
import { toast } from "@/components/ui/use-toast";
import { useModelChange } from "@/core/ai/config";
import { pendingAiPromptAtom } from "@/core/ai/state";
import type { CopilotMode } from "@/core/ai/tools/registry";
import { aiModelConfiguredAtom } from "@/core/config/config";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { useChromeActions } from "../state";
import { type AiPanelTab, aiPanelTabAtom, useAiPanelTab } from "./useAiPanel";

export interface OpenAiAssistantOptions {
  prompt: string;
  submit?: boolean;
  /** Override the user's AI sidebar tab. When omitted, the stored tab is used. */
  panel?: AiPanelTab;
  /** Chat copilot mode. Only applied when the chat panel is the target. */
  mode?: CopilotMode;
}

// Resolve which AI panel to open.
export function resolveAiPanelTab(
  panel: AiPanelTab | undefined,
  storedTab: AiPanelTab,
): AiPanelTab {
  if (panel) {
    return panel;
  }
  return getFeatureFlag("external_agents") ? storedTab : "chat";
}

/**
 * Opens the AI assistant sidebar panel and delivers a prompt to it.
 *
 * If no `panel` is given, the user's configured tab is respected.
 */
export function useOpenAiAssistant() {
  const { openApplication } = useChromeActions();
  const { setAiPanelTab } = useAiPanelTab();
  const { saveModeChange } = useModelChange();
  const setPendingPrompt = useSetAtom(pendingAiPromptAtom);
  const store = useStore();

  return useEvent(async (opts: OpenAiAssistantOptions) => {
    const tab = resolveAiPanelTab(opts.panel, store.get(aiPanelTabAtom));

    const chatPanelReady = store.get(aiModelConfiguredAtom);
    const agentsPanelReady =
      getFeatureFlag("external_agents") &&
      store.get(agentSessionStateAtom).sessions.length > 0;
    const isReady = tab === "agents" ? agentsPanelReady : chatPanelReady;

    if (!isReady) {
      toast({
        title: tab === "agents" ? "No agent session" : "AI not configured",
        description:
          tab === "agents"
            ? "Start an agent session or switch to the chat panel."
            : "Configure an AI provider and chat model to fix with AI.",
        variant: "danger",
      });
      return;
    }

    if (opts.panel) {
      setAiPanelTab(opts.panel);
    }
    // Persist the mode before queueing so an auto-submitted prompt uses the
    // requested mode/tools rather than the stale chat mode.
    if (tab === "chat" && opts.mode) {
      await saveModeChange(opts.mode);
    }

    setPendingPrompt({
      prompt: opts.prompt,
      submit: opts.submit ?? false,
    });

    openApplication("ai");
  });
}
