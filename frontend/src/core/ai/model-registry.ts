/* Copyright 2024 Marimo. All rights reserved. */

import type { AiModel as AiModelType } from "@marimo-team/llm-info";
import type { ProviderId } from "./ids/ids";
import { AiModelId, type QualifiedModelId, type ShortModelId } from "./ids/ids";

export interface AiModel extends AiModelType {
  /** Whether this is a custom model. */
  custom: boolean;
}

export class AiModelRegistry {
  private modelsByProviderMap = new Map<ProviderId, AiModel[]>();
  private customModels = new Set<QualifiedModelId>();
  private displayedModels = new Set<QualifiedModelId>();

  private constructor(
    customModels: QualifiedModelId[],
    displayedModels: QualifiedModelId[],
  ) {
    this.customModels = new Set(customModels);
    this.displayedModels = new Set(displayedModels);
  }

  /**
   * @param customModels - A list of custom models to use that are not from the default list.
   * @param displayedModels - A list of models to display in the UI. If empty, all models will be displayed.
   *
   * Models should be in the format of `provider_id/short_model_id`.
   */
  static async create(customModels?: string[], displayedModels?: string[]) {
    const registry = new AiModelRegistry(
      (customModels as QualifiedModelId[]) ?? [],
      (displayedModels as QualifiedModelId[]) ?? [],
    );
    await registry.buildMaps();
    return registry;
  }

  /**
   * Builds the maps of models by provider and custom models.
   * Custom models are added first as they are specified by the user, so we want to surface them first.
   */
  private async buildMaps() {
    const modelsData = await import("@marimo-team/llm-info/models.json");

    const displayedModels = this.displayedModels;
    const hasDisplayedModels = displayedModels.size > 0;

    for (const model of this.customModels) {
      // This will compare the fully qualified model id
      if (hasDisplayedModels && !displayedModels.has(model)) {
        continue;
      }

      const modelId = AiModelId.parse(model);
      const modelInfo: AiModel = {
        name: modelId.shortModelId,
        model: modelId.shortModelId,
        description: "Custom model",
        providers: [modelId.providerId],
        roles: ["chat", "edit"],
        thinking: false,
        custom: true,
      };
      this.modelsByProviderMap.set(modelId.providerId, [
        ...(this.modelsByProviderMap.get(modelId.providerId) || []),
        modelInfo,
      ]);
    }

    for (const model of modelsData.default.models) {
      const modelId = model.model as ShortModelId;
      const modelInfo: AiModel = {
        ...model,
        custom: false,
      } as AiModel;

      for (const provider of model.providers) {
        const qualifiedModelId = `${provider}/${modelId}` as QualifiedModelId;
        if (hasDisplayedModels && !displayedModels.has(qualifiedModelId)) {
          continue;
        }

        this.modelsByProviderMap.set(provider as ProviderId, [
          ...(this.modelsByProviderMap.get(provider as ProviderId) || []),
          modelInfo,
        ]);
      }
    }
  }

  getDisplayedModels() {
    return this.displayedModels;
  }

  getCustomModels() {
    return this.customModels;
  }

  getModelsByProvider(provider: ProviderId) {
    return this.modelsByProviderMap.get(provider) || [];
  }

  getGroupedModelsByProvider() {
    return this.modelsByProviderMap;
  }
}
