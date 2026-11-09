/* Copyright 2026 Marimo. All rights reserved. */

import { DEFAULT_AI_MODEL, type AiConfig } from "@/core/config/config-schema";
import type { ChatOptions } from "@/core/network/types";
import { AiModelId } from "./ids/ids";
import { AiModelRegistry } from "./model-registry";
import {
  getChatReasoningEffortOptions,
  type ReasoningEffortChoice,
} from "./reasoning-options";

export function getChatModelConfig(ai: AiConfig | undefined) {
  const current = AiModelId.parse(ai?.models?.chat_model || DEFAULT_AI_MODEL);
  const displayedModels = ai?.models?.displayed_models ?? [];
  const registry = AiModelRegistry.create({
    customModels: [...(ai?.models?.custom_models ?? []), current.id],
    displayedModels:
      displayedModels.length > 0 ? [...displayedModels, current.id] : [],
  });
  const currentModel = registry.getModel(current.id);
  return {
    current,
    registry,
    displayName: currentModel?.name ?? current.shortModelId,
    reasoningOptions: getChatReasoningEffortOptions(
      currentModel,
      ai?.open_ai?.base_url,
    ),
  };
}

export function getEffectiveChatOptions(
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
