/* Copyright 2026 Marimo. All rights reserved. */

import { DEFAULT_AI_MODEL, type AiConfig } from "@/core/config/config-schema";
import type { ChatOptions } from "@/core/network/types";
import { AiModelId } from "./ids/ids";
import { AiModelRegistry, getKnownModelMaps } from "./model-registry";
import {
  getChatReasoningOptions,
  type ReasoningEffortChoice,
} from "./reasoning-options";

export function getChatModelId(ai: AiConfig | undefined) {
  return AiModelId.parse(
    ai?.models?.chat_model || ai?.open_ai?.model || DEFAULT_AI_MODEL,
  );
}

export function getChatModelConfig(
  ai: AiConfig | undefined,
  autocompleteModel?: string | null,
) {
  const current = getChatModelId(ai);
  const displayedModels = ai?.models?.displayed_models ?? [];
  const knownModels = getKnownModelMaps().modelMap;
  const registry = AiModelRegistry.create({
    customModels: [
      ...(ai?.models?.custom_models ?? []),
      current.id,
      autocompleteModel,
      ai?.models?.edit_model,
    ]
      .filter(Boolean)
      .filter((model) => !knownModels.has(AiModelId.parse(model).id)),
    displayedModels:
      displayedModels.length > 0 ? [...displayedModels, current.id] : [],
  });
  const currentModel = registry.getModel(current.id);
  return {
    current,
    registry,
    reasoningOptions: getChatReasoningOptions(currentModel),
    displayName: currentModel?.name ?? current.shortModelId,
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
