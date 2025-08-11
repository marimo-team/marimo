/* Copyright 2024 Marimo. All rights reserved. */

import type { TypedString } from "../typed";

/**
 * Supported providers by the marimo server.
 */
export type ProviderId =
  | "openai"
  | "anthropic"
  | "google"
  | "ollama"
  | "bedrock";

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

  static parse(id: QualifiedModelId) {
    if (!id.includes("/")) {
      const providerId = guessProviderId(id);
      return new AiModelId(providerId, id as ShortModelId);
    }

    const [providerId, shortModelId] = id.split("/");
    return new AiModelId(
      providerId as ProviderId,
      shortModelId as ShortModelId,
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
  return "ollama";
}
