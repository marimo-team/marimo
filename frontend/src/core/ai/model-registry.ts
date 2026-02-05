/* Copyright 2026 Marimo. All rights reserved. */

import type {
  AiModel as AiModelType,
  AiProvider,
  Role,
} from "@marimo-team/llm-info";
import { models } from "@marimo-team/llm-info/models.json";
import { providers } from "@marimo-team/llm-info/providers.json";
import { Logger } from "@/utils/Logger";
import { MultiMap } from "@/utils/multi-map";
import { once } from "@/utils/once";
import type { ProviderId } from "./ids/ids";
import { AiModelId, type QualifiedModelId, type ShortModelId } from "./ids/ids";

export interface AiModel extends AiModelType {
  roles: Role[];
  model: ShortModelId;
  providers: ProviderId[];
  /** Whether this is a custom model. */
  custom: boolean;
}

interface KnownModelMaps {
  /** Map of qualified model ID to model info */
  modelMap: ReadonlyMap<QualifiedModelId, AiModel>;
  /** Map of provider ID to first default model (supports chat or edit) */
  defaultModelByProvider: ReadonlyMap<ProviderId, QualifiedModelId>;
}

export const getKnownModelMaps = once((): KnownModelMaps => {
  const modelMap = new Map<QualifiedModelId, AiModel>();
  const defaultModelByProvider = new Map<ProviderId, QualifiedModelId>();

  for (const model of models) {
    const modelId = model.model as ShortModelId;
    const modelInfo: AiModel = {
      ...model,
      model: model.model as ShortModelId,
      roles: model.roles.map((role) => role as Role),
      providers: model.providers as ProviderId[],
      custom: false,
    };

    const supportsChatOrEdit =
      modelInfo.roles.includes("chat") || modelInfo.roles.includes("edit");

    for (const provider of modelInfo.providers) {
      const qualifiedModelId: QualifiedModelId = `${provider}/${modelId}`;
      modelMap.set(qualifiedModelId, modelInfo);

      // Track first model per provider that supports chat or edit
      if (supportsChatOrEdit && !defaultModelByProvider.has(provider)) {
        defaultModelByProvider.set(provider, qualifiedModelId);
      }
    }
  }

  return { modelMap, defaultModelByProvider };
});

const getProviderMap = once(
  (): {
    providerMap: ReadonlyMap<ProviderId, AiProvider>;
    providerToOrderIdx: ReadonlyMap<ProviderId, number>;
  } => {
    const providerMap = new Map<ProviderId, AiProvider>();
    const providerToOrderIdx = new Map<ProviderId, number>();
    providers.forEach((provider, idx) => {
      const providerId = provider.id as ProviderId;
      providerMap.set(providerId, provider);
      providerToOrderIdx.set(providerId, idx);
    });
    return { providerMap, providerToOrderIdx };
  },
);

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
    const { providerMap } = getProviderMap();
    return providerMap.get(providerId);
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
    let result = AiModelRegistry.buildMapsFromConfig({
      displayedModels: this.displayedModels,
      customModels: this.customModels,
    });

    // If we got zero results, then build the maps with no displayedModels
    // This can happen if displayedModels is configured to non existent models
    if (result.modelsMap.size === 0) {
      Logger.error(
        "The configured displayed_models have filtered out all registered models. Reverting back to showing all models.",
        [...this.displayedModels],
      );

      result = AiModelRegistry.buildMapsFromConfig({
        displayedModels: new Set(),
        customModels: this.customModels,
      });
    }

    this.modelsByProviderMap = result.modelsByProviderMap;
    this.modelsMap = result.modelsMap;
  }

  private static buildMapsFromConfig(opts: {
    customModels: ReadonlySet<QualifiedModelId>;
    displayedModels: ReadonlySet<QualifiedModelId>;
  }) {
    const { displayedModels, customModels } = opts;
    const hasDisplayedModels = displayedModels.size > 0;
    const knownModelMap = getKnownModelMaps().modelMap;
    const customModelsMap = new Map<QualifiedModelId, AiModel>();

    let modelsMap = new Map<QualifiedModelId, AiModel>();
    const modelsByProviderMap = new MultiMap<ProviderId, AiModel>();

    for (const model of customModels) {
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
    // Known models will overwrite custom models (which is desired)
    modelsMap = new Map([...customModelsMap, ...modelsMap]);

    // Group by provider
    for (const [qualifiedModelId, model] of modelsMap.entries()) {
      const modelId = AiModelId.parse(qualifiedModelId);
      modelsByProviderMap.add(modelId.providerId, model);
    }

    return { modelsByProviderMap, modelsMap };
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

  getListModelsByProvider(): [ProviderId, AiModel[]][] {
    const modelsByProvider = this.getGroupedModelsByProvider();
    const arrayModels = [...modelsByProvider.entries()];
    const providerToOrderIdx = getProviderMap().providerToOrderIdx;

    arrayModels.sort((a, b) => {
      const aProvider = a[0];
      const bProvider = b[0];
      const aOrderIdx = providerToOrderIdx.get(aProvider) ?? 0;
      const bOrderIdx = providerToOrderIdx.get(bProvider) ?? 0;
      return aOrderIdx - bOrderIdx;
    });
    return arrayModels;
  }

  getModelsMap() {
    return this.modelsMap;
  }

  getModel(qualifiedModelId: QualifiedModelId) {
    return this.modelsMap.get(qualifiedModelId);
  }
}
