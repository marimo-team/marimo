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
  github: (ai) => Boolean(ai?.github?.api_key),
  openrouter: (ai) => Boolean(ai?.openrouter?.api_key),
  azure: (ai) => Boolean(ai?.azure?.api_key && ai?.azure?.base_url),
  wandb: (ai) => Boolean(ai?.wandb?.api_key),
  bedrock: (ai) => Boolean(ai?.bedrock?.region_name),
  ollama: (ai) => Boolean(ai?.ollama?.base_url),
  // These providers don't have user-configurable credentials in the UI
  deepseek: () => false,
  marimo: () => false,
};

/**
 * Returns the first configured provider based on credentials.
 */
export function getConfiguredProvider(
  config: UserConfig,
): ProviderId | undefined {
  const ai = config.ai;

  for (const provider of KNOWN_PROVIDERS) {
    if (CREDENTIAL_CHECKERS[provider](ai)) {
      return provider;
    }
  }

  // Check custom providers
  const customProviders = ai?.custom_providers;
  if (customProviders) {
    const firstCustomProvider = Object.entries(customProviders).find(
      ([_, providerConfig]) => providerConfig?.base_url,
    );
    if (firstCustomProvider) {
      return firstCustomProvider[0];
    }
  }
}

export function getRecommendedModel(config: UserConfig): string | undefined {
  const provider = getConfiguredProvider(config);
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
export function autoPopulateModels(values: UserConfig): AutoPopulateResult {
  const result: AutoPopulateResult = {
    chatModel: undefined,
    editModel: undefined,
  };

  const needsChatModel = !values.ai?.models?.chat_model;
  const needsEditModel = !values.ai?.models?.edit_model;

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
