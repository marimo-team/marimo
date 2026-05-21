/* Copyright 2026 Marimo. All rights reserved. */

import type { AiModel, ModelsByProvider, ProviderId, Role } from "../index.ts";
import type { ModelsDevApi, ModelsDevModel } from "./models-dev.ts";

/**
 * Allowlist of models.dev provider ids → marimo provider ids. Models from
 * providers outside this map are ignored. To opt a provider in, add it to
 * `providers.yml` and register it here.
 */
export const PROVIDER_MAP = {
  anthropic: "anthropic",
  openai: "openai",
  google: "google",
  "google-vertex": "google",
  "amazon-bedrock": "bedrock",
  azure: "azure",
  "github-models": "github",
  "ollama-cloud": "ollama",
  wandb: "wandb",
  "opencode-go": "opencode-go",
} as const satisfies Readonly<Record<string, ProviderId>>;

const MODALITIES = new Set(["text", "image", "pdf"]);

/** Sentinel for models with no `release_date` upstream — sorts to the bottom. */
const UNKNOWN_DATE = new Date("1970-01-01");
export const MAX_MODELS_PER_PROVIDER = 10;

/**
 * Loose shape for entries read from `models.yml` — we only need the `model` id
 * to detect duplicates within a provider section.
 */
export type ExistingEntry = Readonly<{ model: string }>;
export type ExistingByProvider = Readonly<
  Record<string, readonly ExistingEntry[]>
>;

export interface MergeSummary {
  /** New entries grouped by provider id, ready to merge into `models.yml`. */
  newEntries: ModelsByProvider;
  preservedCount: number;
  /** `provider/model` ids skipped because they already exist locally. */
  skippedExisting: string[];
}

function deriveRoles(model: ModelsDevModel): Role[] {
  const id = model.id.toLowerCase();
  const name = model.name.toLowerCase();
  if (id.includes("embed") || name.includes("embedding")) {
    return ["embed"];
  }
  if (id.includes("rerank") || name.includes("rerank")) {
    return ["rerank"];
  }
  return ["chat", "edit"];
}

function deriveCapabilities(model: ModelsDevModel): AiModel["capabilities"] {
  const capabilities: AiModel["capabilities"] = [];
  if (model.reasoning) {
    capabilities.push("thinking");
  }
  if (model.tool_call) {
    capabilities.push("tool_calling");
  }
  return capabilities;
}

function filterModalities(
  modalities: readonly string[] | undefined,
): AiModel["input_types"] {
  if (!modalities) {
    return [];
  }
  return modalities.filter((m): m is "text" | "image" | "pdf" =>
    MODALITIES.has(m),
  );
}

/** Upstream `release_date` is sometimes `YYYY-MM`; pad and parse defensively. */
function parseReleaseDate(raw: string | undefined): Date {
  if (!raw) {
    return UNKNOWN_DATE;
  }
  const normalized = /^\d{4}-\d{2}$/.test(raw) ? `${raw}-01` : raw;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? UNKNOWN_DATE : date;
}

function deriveCost(source: ModelsDevModel): AiModel["cost"] {
  const { input, output } = source.cost ?? {};
  if (typeof input !== "number" && typeof output !== "number") {
    return undefined;
  }
  return {
    ...(typeof input === "number" && { input }),
    ...(typeof output === "number" && { output }),
  };
}

function buildAiModel(source: ModelsDevModel): AiModel {
  const cost = deriveCost(source);
  return {
    name: source.name,
    model: source.id,
    description: "",
    roles: deriveRoles(source),
    capabilities: deriveCapabilities(source),
    input_types: filterModalities(source.modalities?.input),
    output_types: filterModalities(source.modalities?.output),
    release_date: parseReleaseDate(source.release_date),
    ...(cost && { cost }),
  };
}

/**
 * Sort newest-first by `release_date` and trim to `maxPerProvider`. Tie-break
 * on model id so identical dates produce a deterministic order.
 */
function sortAndTrim(entries: AiModel[], maxPerProvider: number): AiModel[] {
  const sorted = [...entries].sort((a, b) => {
    const dateDelta = b.release_date.getTime() - a.release_date.getTime();
    if (dateDelta !== 0) {
      return dateDelta;
    }
    return a.model.localeCompare(b.model);
  });
  return sorted.slice(0, maxPerProvider);
}

export interface MergeOptions {
  /** Defaults to {@link MAX_MODELS_PER_PROVIDER}. */
  maxPerProvider?: number;
  /**
   * Restrict the sync to these marimo provider ids. Defaults to all providers
   * in {@link PROVIDER_MAP}.
   */
  providers?: readonly string[];
}

/**
 * Merge models.dev data into existing per-provider entries.
 *
 * - Existing entries (matched by `(provider, model)` id pair) are never
 *   modified — all human curation is preserved.
 * - New entries are added with `description: ""` for the human to fill in.
 * - Idempotent: a second run with the same inputs produces no new entries.
 */
export function mergeModels(
  existing: ExistingByProvider,
  modelsDev: ModelsDevApi,
  options: MergeOptions = {},
): MergeSummary {
  const { maxPerProvider = MAX_MODELS_PER_PROVIDER, providers } = options;
  const providerFilter = providers ? new Set(providers) : null;
  const newEntries: ModelsByProvider = {};
  const skippedExisting: string[] = [];
  let preservedCount = 0;

  for (const [provider, entries] of Object.entries(existing)) {
    if (providerFilter && !providerFilter.has(provider)) {
      continue;
    }
    preservedCount += entries.length;
  }

  for (const [devProviderId, marimoProviderId] of Object.entries(
    PROVIDER_MAP,
  )) {
    if (providerFilter && !providerFilter.has(marimoProviderId)) {
      continue;
    }
    const provider = modelsDev[devProviderId];
    if (!provider) {
      continue;
    }
    const existingIds = new Set(
      (existing[marimoProviderId] ?? []).map((m) => m.model),
    );

    const candidates: AiModel[] = [];
    for (const model of Object.values(provider.models)) {
      if (existingIds.has(model.id)) {
        skippedExisting.push(`${marimoProviderId}/${model.id}`);
        continue;
      }
      candidates.push(buildAiModel(model));
    }

    if (candidates.length > 0) {
      const trimmed = sortAndTrim(candidates, maxPerProvider);
      const existingBucket = newEntries[marimoProviderId];
      if (existingBucket) {
        existingBucket.push(...trimmed);
      } else {
        newEntries[marimoProviderId] = trimmed;
      }
    }
  }

  return { newEntries, preservedCount, skippedExisting };
}
