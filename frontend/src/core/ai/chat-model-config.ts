/* Copyright 2026 Marimo. All rights reserved. */

import {
  DEFAULT_AI_MODEL,
  type AiConfig,
  type UserConfig,
} from "@/core/config/config-schema";
import type { ChatOptions } from "@/core/network/types";
import { AiModelId } from "./ids/ids";
import {
  AiModelRegistry,
  getKnownModelMaps,
  listConfiguredModelIds,
} from "./model-registry";
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
  copilot: UserConfig["completion"]["copilot"] = false,
) {
  const current = getChatModelId(ai);
  const displayedModels = ai?.models?.displayed_models ?? [];
  const knownModels = getKnownModelMaps().modelMap;
  const registry = AiModelRegistry.create({
    customModels: listConfiguredModelIds(
      { ...ai?.models, chat_model: current.id },
      copilot,
    ).filter((model) => !knownModels.has(AiModelId.parse(model).id)),
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
