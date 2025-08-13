/* Copyright 2024 Marimo. All rights reserved. */

import type { TypedString } from "../typed";

/**
 * Supported providers by the marimo server.
 */
const KNOWN_AI_PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "ollama",
  "bedrock",
  "deepseek",
] as const;
export type ProviderId = (typeof KNOWN_AI_PROVIDERS)[number];

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

export function isKnownAIProvider(providerId: ProviderId): boolean {
  return KNOWN_AI_PROVIDERS.includes(providerId);
}
