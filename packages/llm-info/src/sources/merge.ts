/* Copyright 2026 Marimo. All rights reserved. */

import type {
  AiModel,
  ModelsByProvider,
  Role,
  SyncableProviderId,
} from "../index.ts";
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
} as const satisfies Readonly<Record<string, SyncableProviderId>>;

const MODALITIES = new Set(["text", "image", "pdf"]);

/** Sentinel for models with no `release_date` upstream — sorts to the bottom. */
const UNKNOWN_DATE = "1970-01-01";
export const MAX_MODELS_PER_PROVIDER = 10;

/**
 * Frontier-tier price ceilings, in USD per million tokens.
 */
export const MAX_COST_INPUT = 30;
export const MAX_COST_OUTPUT = 100;

/**
 * Per-provider explicit denylist of model ids.

 * Note: this only blocks future appends. To remove a model that's already
 * in `models.yml`, delete the entry by hand.
 */
export const MODEL_DENYLIST: Readonly<Record<string, ReadonlySet<string>>> = {
  openai: new Set([
    // Surfaced inside ChatGPT only; not exposed via the OpenAI API.
    "gpt-5.3-codex-spark",
  ]),
};

function isDenylisted(marimoProviderId: string, modelId: string): boolean {
  return MODEL_DENYLIST[marimoProviderId]?.has(modelId) ?? false;
}

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

/**
 * Normalize upstream `release_date` to `YYYY-MM-DD`. Accepts shorthand
 * (`YYYY-MM`), full ISO timestamps, and anything else `Date.parse` understands
 * — but always emits the canonical `YYYY-MM-DD` form so downstream lex-sort
 * and the `AiModel.release_date` type contract hold. Unparsable / missing
 * values fall back to the sentinel.
 */
function parseReleaseDate(raw: string | undefined): string {
  if (!raw) {
    return UNKNOWN_DATE;
  }
  // Pad `YYYY-MM` shorthand to first of month before parsing.
  const padded = /^\d{4}-\d{2}$/.test(raw) ? `${raw}-01` : raw;
  const ms = Date.parse(padded);
  if (Number.isNaN(ms)) {
    return UNKNOWN_DATE;
  }
  return new Date(ms).toISOString().slice(0, 10);
}

function isWithinCostBudget(source: ModelsDevModel): boolean {
  const cost = source.cost ?? {};
  if (typeof cost.input === "number" && cost.input >= MAX_COST_INPUT) {
    return false;
  }
  if (typeof cost.output === "number" && cost.output >= MAX_COST_OUTPUT) {
    return false;
  }
  return true;
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
    // ISO `YYYY-MM-DD` strings sort lexicographically the same as by date.
    if (a.release_date !== b.release_date) {
      return a.release_date < b.release_date ? 1 : -1;
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
 * Pipeline per provider:
 *   1. Collect upstream candidates, dropping anything above the cost ceilings
 *      or explicitly listed in `MODEL_DENYLIST`.
 *   2. Sort newest-first and trim to `maxPerProvider` — this is what `-n N`
 *      means: "the N freshest models upstream is exposing right now."
 *   3. Of that top-N, drop ids we already have locally; the remainder is what
 *      gets appended.
 *
 * Consequences worth knowing:
 * - Existing entries (matched by `(provider, model)` id pair) are never
 *   modified — all human curation is preserved.
 * - New entries are added with `description: ""` for the human to fill in.
 * - Idempotent: a second run with the same inputs produces no new entries.
 * - If every model in the top-N is already curated, this run adds zero —
 *   we don't backfill with older "missing" models.
 */
export function mergeModels(
  existing: ExistingByProvider,
  modelsDev: ModelsDevApi,
  options: MergeOptions = {},
): MergeSummary {
  const { maxPerProvider = MAX_MODELS_PER_PROVIDER, providers } = options;
  const providerFilter = providers ? new Set(providers) : null;
  const skippedExisting: string[] = [];
  let preservedCount = 0;

  for (const [provider, entries] of Object.entries(existing)) {
    if (providerFilter && !providerFilter.has(provider)) {
      continue;
    }
    preservedCount += entries.length;
  }

  // Multiple models.dev provider ids can map to the same marimo provider
  // (e.g. `google` + `google-vertex` → `google`). Accumulate candidates per
  // marimo provider id, de-duplicating by model id, before sorting + trimming.
  const candidatesByProvider = new Map<string, Map<string, AiModel>>();

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
    const bucket =
      candidatesByProvider.get(marimoProviderId) ?? new Map<string, AiModel>();

    for (const model of Object.values(provider.models)) {
      if (!isWithinCostBudget(model)) {
        continue;
      }
      if (isDenylisted(marimoProviderId, model.id)) {
        continue;
      }
      // First mapped source wins on conflict — later iterations skip dupes.
      if (!bucket.has(model.id)) {
        bucket.set(model.id, buildAiModel(model));
      }
    }
    candidatesByProvider.set(marimoProviderId, bucket);
  }

  const newEntries: ModelsByProvider = {};
  for (const [marimoProviderId, bucket] of candidatesByProvider) {
    if (bucket.size === 0) {
      continue;
    }
    const topN = sortAndTrim([...bucket.values()], maxPerProvider);
    const existingIds = new Set(
      (existing[marimoProviderId] ?? []).map((m) => m.model),
    );
    const fresh: AiModel[] = [];
    for (const entry of topN) {
      if (existingIds.has(entry.model)) {
        skippedExisting.push(`${marimoProviderId}/${entry.model}`);
        continue;
      }
      fresh.push(entry);
    }
    if (fresh.length > 0) {
      newEntries[marimoProviderId as SyncableProviderId] = fresh;
    }
  }

  return { newEntries, preservedCount, skippedExisting };
}
