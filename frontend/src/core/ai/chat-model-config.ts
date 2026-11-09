/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { aiAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { AiModelId } from "./ids/ids";
import { AiModelRegistry } from "./model-registry";
import { getChatReasoningEffortOptions } from "./reasoning-options";
import { chatOptionsAtom } from "./state";

export const chatModelConfigAtom = atom((get) => {
  const ai = get(aiAtom);
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
    reasoningOptions: getChatReasoningEffortOptions(currentModel, ai),
  };
});

export const effectiveChatOptionsAtom = atom((get) => {
  const options = get(chatOptionsAtom);
  const { reasoningOptions } = get(chatModelConfigAtom);
  const effort = options.reasoningEffort;
  return {
    ...options,
    reasoningEffort: reasoningOptions.some((option) => option.value === effort)
      ? effort
      : null,
  };
});
