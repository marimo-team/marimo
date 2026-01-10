/* Copyright 2026 Marimo. All rights reserved. */

import type { TypedString } from "@/utils/typed";

export const KNOWN_PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "ollama",
  "bedrock",
  "deepseek",
  "azure",
  "github",
  "openrouter",
  "wandb",
  "marimo",
] as const;
export type KnownProviderId = (typeof KNOWN_PROVIDERS)[number];

/**
 * Provider ID can be a known provider or a custom string
 * The (string & {}) pattern allows any string while still providing autocomplete for known providers
 */
export type ProviderId = KnownProviderId | (string & {});

export type ShortModelId = TypedString<"ShortModelId">;

/**
 * Qualified model id
 * `provider_id/short_model_id`;
 */
export type QualifiedModelId = `${ProviderId}/${ShortModelId}`;

export class AiModelId {
  readonly providerId: ProviderId;
  readonly shortModelId: ShortModelId;

  constructor(providerId: ProviderId, shortModelId: ShortModelId) {
    this.providerId = providerId;
    this.shortModelId = shortModelId;
  }

  get id(): QualifiedModelId {
    return `${this.providerId}/${this.shortModelId}`;
  }

  static parse(id: string): AiModelId {
    if (!id.includes("/")) {
      const providerId = guessProviderId(id);
      return new AiModelId(providerId, id as ShortModelId);
    }

    const [providerId, ...shortModelId] = id.split("/");
    return new AiModelId(
      providerId as ProviderId,
      shortModelId.join("/") as ShortModelId,
    );
  }
}

function guessProviderId(id: string): ProviderId {
  if (id.startsWith("gpt") || id.startsWith("o3") || id.startsWith("o1")) {
    return "openai";
  }
  if (id.startsWith("claude")) {
    return "anthropic";
  }
  if (id.startsWith("gemini") || id.startsWith("google")) {
    return "google";
  }
  if (id.startsWith("deepseek")) {
    return "deepseek";
  }
  return "ollama";
}

export function isKnownAIProvider(
  providerId: string,
): providerId is KnownProviderId {
  return (KNOWN_PROVIDERS as readonly string[]).includes(providerId);
}
