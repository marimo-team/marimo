/* Copyright 2026 Marimo. All rights reserved. */

import { dequal } from "dequal";
import { atom } from "jotai";
import { selectAtom } from "jotai/utils";
import { aiAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import type { ChatOptions } from "@/core/network/types";
import { AiModelId } from "./ids/ids";
import { AiModelRegistry } from "./model-registry";
import {
  getChatReasoningEffortOptions,
  type ReasoningEffortChoice,
} from "./reasoning-options";
import { chatOptionsAtom } from "./state";

const chatModelSettingsAtom = selectAtom(
  aiAtom,
  (ai) => ({
    modelId: ai?.models?.chat_model || DEFAULT_AI_MODEL,
    customModels: ai?.models?.custom_models ?? [],
    displayedModels: ai?.models?.displayed_models ?? [],
    openAiBaseUrl: ai?.open_ai?.base_url,
  }),
  dequal,
);

export const chatModelConfigAtom = selectAtom(
  chatModelSettingsAtom,
  (settings) => {
    const current = AiModelId.parse(settings.modelId);
    const registry = AiModelRegistry.create({
      customModels: [...settings.customModels, current.id],
      displayedModels:
        settings.displayedModels.length > 0
          ? [...settings.displayedModels, current.id]
          : [],
    });
    const currentModel = registry.getModel(current.id);
    return {
      current,
      registry,
      displayName: currentModel?.name ?? current.shortModelId,
      reasoningOptions: getChatReasoningEffortOptions(
        currentModel,
        settings.openAiBaseUrl,
      ),
    };
  },
);

function getEffectiveChatOptions(
  options: ChatOptions & { webSearch: boolean },
  reasoningOptions: ReasoningEffortChoice[],
) {
  const effort = options.reasoningEffort;
  return {
    ...options,
    reasoningEffort: reasoningOptions.some((option) => option.value === effort)
      ? effort
      : null,
  };
}

export const effectiveChatOptionsAtom = selectAtom(
  atom((get) =>
    getEffectiveChatOptions(
      get(chatOptionsAtom),
      get(chatModelConfigAtom).reasoningOptions,
    ),
  ),
  (options) => options,
  dequal,
);
