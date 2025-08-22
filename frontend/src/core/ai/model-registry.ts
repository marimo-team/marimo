/* Copyright 2024 Marimo. All rights reserved. */

import type {
  AiModel as AiModelType,
  AiProvider,
  Role,
} from "@marimo-team/llm-info";
import { models } from "@marimo-team/llm-info/models.json";
import { providers } from "@marimo-team/llm-info/providers.json";
import { MultiMap } from "@/utils/multi-map";
import { once } from "@/utils/once";
import type { ProviderId } from "./ids/ids";
import { AiModelId, type QualifiedModelId, type ShortModelId } from "./ids/ids";

export interface AiModel extends AiModelType {
  roles: Role[];
  providers: ProviderId[];
  /** Whether this is a custom model. */
  custom: boolean;
}

const getKnownModelMap = once((): ReadonlyMap<QualifiedModelId, AiModel> => {
  const modelMap = new Map<QualifiedModelId, AiModel>();
  for (const model of models) {
    const modelId = model.model as ShortModelId;
    const modelInfo: AiModel = {
      ...model,
      roles: model.roles.map((role) => role as Role),
      providers: model.providers as ProviderId[],
      custom: false,
    };

    for (const provider of modelInfo.providers) {
      const qualifiedModelId: QualifiedModelId = `${provider}/${modelId}`;
      modelMap.set(qualifiedModelId, modelInfo);
    }
  }
  return modelMap;
});

const getProviderMap = once((): ReadonlyMap<ProviderId, AiProvider> => {
  const providerMap = new Map<ProviderId, AiProvider>();
  for (const provider of providers) {
    providerMap.set(provider.id as ProviderId, provider);
  }
  return providerMap;
});

export class AiModelRegistry {
  private modelsByProviderMap = new MultiMap<ProviderId, AiModel>();
  private modelsMap: ReadonlyMap<QualifiedModelId, AiModel>;
  private customModels: ReadonlySet<QualifiedModelId>;
  private displayedModels: ReadonlySet<QualifiedModelId>;

  private constructor(
    customModels: QualifiedModelId[],
    displayedModels: QualifiedModelId[],
  ) {
    this.customModels = new Set(customModels);
    this.displayedModels = new Set(displayedModels);
    this.modelsMap = new Map<QualifiedModelId, AiModel>();
    this.buildMaps();
  }

  static getProviderInfo(providerId: ProviderId) {
    return getProviderMap().get(providerId);
  }

  /**
   * @param customModels - A list of custom models to use that are not from the default list.
   * @param displayedModels - A list of models to display in the UI. If empty, all models will be displayed.
   *
   * Models should be in the format of `provider_id/short_model_id`.
   */
  static create(opts: { customModels?: string[]; displayedModels?: string[] }) {
    const { customModels = [], displayedModels = [] } = opts;
    return new AiModelRegistry(
      customModels.map((model) => AiModelId.parse(model).id),
      displayedModels.map((model) => AiModelId.parse(model).id),
    );
  }

  /**
   * Builds the maps of models by provider and custom models.
   */
  private buildMaps() {
    const displayedModels = this.displayedModels;
    const hasDisplayedModels = displayedModels.size > 0;
    const knownModelMap = getKnownModelMap();
    const customModelsMap = new Map<QualifiedModelId, AiModel>();

    let modelsMap = new Map<QualifiedModelId, AiModel>();

    for (const model of this.customModels) {
      if (hasDisplayedModels && !displayedModels.has(model)) {
        continue;
      }
      const modelId = AiModelId.parse(model);
      const modelInfo: AiModel = {
        name: modelId.shortModelId,
        model: modelId.shortModelId,
        description: "Custom model",
        providers: [modelId.providerId],
        roles: [],
        thinking: false,
        custom: true,
      };
      customModelsMap.set(model, modelInfo);
    }

    // Add known models
    if (hasDisplayedModels) {
      for (const model of displayedModels) {
        const modelInfo = knownModelMap.get(model);
        if (modelInfo) {
          modelsMap.set(model, modelInfo);
        }
      }
    } else {
      modelsMap = new Map(knownModelMap);
    }

    // Set custom models first, then known models
    modelsMap = new Map([...customModelsMap, ...modelsMap]);

    // Group by provider
    for (const [qualifiedModelId, model] of modelsMap.entries()) {
      const modelId = AiModelId.parse(qualifiedModelId);
      this.modelsByProviderMap.add(modelId.providerId, model);
    }

    this.modelsMap = modelsMap;
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

  getModelsMap() {
    return this.modelsMap;
  }

  getModel(qualifiedModelId: QualifiedModelId) {
    return this.modelsMap.get(qualifiedModelId);
  }
}
