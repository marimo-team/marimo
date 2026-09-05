/* Copyright 2026 Marimo. All rights reserved. */

import {
  KNOWN_PROVIDERS,
  type KnownProviderId,
  type ProviderId,
} from "@/core/ai/ids/ids";
import { getKnownModelMaps } from "@/core/ai/model-registry";
import type { AiConfig, UserConfig } from "@/core/config/config-schema";

type CredentialChecker = (ai: AiConfig | undefined) => boolean;

/**
 * Credential checkers for each known provider.
 */
const CREDENTIAL_CHECKERS: Record<KnownProviderId, CredentialChecker> = {
  openai: (ai) => Boolean(ai?.open_ai?.api_key),
  anthropic: (ai) => Boolean(ai?.anthropic?.api_key),
  google: (ai) => Boolean(ai?.google?.api_key),
  openrouter: (ai) => Boolean(ai?.openrouter?.api_key),
  azure: (ai) => Boolean(ai?.azure?.api_key && ai?.azure?.base_url),
  wandb: (ai) => Boolean(ai?.wandb?.api_key),
  "opencode-go": (ai) => Boolean(ai?.opencode_go?.api_key),
  bedrock: (ai) => Boolean(ai?.bedrock?.region_name),
  ollama: (ai) => Boolean(ai?.ollama?.base_url),
  // No user-configurable credentials in the UI.
  deepseek: () => false,
  // Hosted marimo models (marimo.app / molab) route through open_ai_compatible.
  marimo: (ai) => Boolean(ai?.open_ai_compatible?.base_url),
};

/**
 * Known providers with credentials, then custom providers with a base URL.
 */
export function listConfiguredProviders(
  ai: AiConfig | undefined,
): ProviderId[] {
  const knownProviders = KNOWN_PROVIDERS.filter((provider) =>
    CREDENTIAL_CHECKERS[provider](ai),
  );
  const customProviders = Object.entries(ai?.custom_providers ?? {})
    .filter(([, providerConfig]) => Boolean(providerConfig?.base_url))
    .map(([name]) => name);
  return [...knownProviders, ...customProviders];
}

/**
 * Keep provider groups whose provider has credentials configured.
 */
export function filterToConfiguredProviders<T>(
  entries: readonly [ProviderId, T][],
  ai: AiConfig | undefined,
): [ProviderId, T][] {
  const configured = new Set<string>(listConfiguredProviders(ai));
  return entries.filter(([provider]) => configured.has(provider));
}

/**
 * When provider setup is locked, only show models for configured providers.
 */
export function listModelsForAiSettings<T>(
  entries: readonly [ProviderId, T][],
  ai: AiConfig | undefined,
): [ProviderId, T][] {
  if (ai?.allow_provider_config !== false) {
    return [...entries];
  }
  return filterToConfiguredProviders(entries, ai);
}

export function getRecommendedModel(
  config: UserConfig["ai"],
): string | undefined {
  const provider = listConfiguredProviders(config)[0];
  if (!provider) {
    return undefined;
  }
  return getKnownModelMaps().defaultModelByProvider.get(provider);
}

export interface AutoPopulateResult {
  chatModel: string | undefined;
  editModel: string | undefined;
}

/**
 * Determines which models to auto-populate based on configured credentials.
 * Returns the recommended model for chat/edit if credentials are configured but models aren't set.
 *
 * @param values - The full form values
 */
export function autoPopulateModels(
  values: UserConfig["ai"],
): AutoPopulateResult {
  const result: AutoPopulateResult = {
    chatModel: undefined,
    editModel: undefined,
  };

  const needsChatModel = !values?.models?.chat_model;
  const needsEditModel = !values?.models?.edit_model;

  if (!needsChatModel && !needsEditModel) {
    return result;
  }

  const recommendedModel = getRecommendedModel(values);
  if (!recommendedModel) {
    return result;
  }

  if (needsChatModel) {
    result.chatModel = recommendedModel;
  }
  if (needsEditModel) {
    result.editModel = recommendedModel;
  }
  return result;
}
