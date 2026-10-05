#!/usr/bin/env node
/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import {
  Document,
  isMap,
  isSeq,
  isScalar,
  parseDocument,
  type YAMLMap,
  type YAMLSeq,
} from "yaml";
import { parseCliArgs } from "./cli.ts";
import type { AiModel, ModelsByProvider } from "./index.ts";
import { ExistingMetadataSchema } from "./metadata.ts";
import { Logger } from "./simple_logger.ts";
import {
  type ExistingByProvider,
  type ExistingEntry,
  MAX_MODELS_PER_PROVIDER,
  mergeModels,
  deriveMetadataUpdates,
  PROVIDER_MAP,
} from "./sources/merge.ts";
import { fetchModelsDev, type ModelsDevApi } from "./sources/models-dev.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * - `append`: keep existing entries, add only what's new (default).
 * - `replace`: overwrite the file with a fresh sync — destructive, for
 *   bootstrapping or regenerating from scratch.
 */
export type SyncMode = "append" | "replace";

interface SyncOptions {
  modelsYamlPath: string;
  /** Pre-loaded api.json for testing; otherwise fetched live. */
  modelsDev?: ModelsDevApi;
  write?: boolean;
  mode?: SyncMode;
  /** Refresh metadata on curated entries without adding models. */
  metadataOnly?: boolean;
  /** Cap on new entries inserted per provider section. */
  maxPerProvider?: number;
  /** Restrict sync to these marimo provider ids (defaults to all). */
  providers?: readonly string[];
}

export interface SyncResult {
  added: number;
  preserved: number;
  updated: number;
  yaml: string;
}

/** Sequence keys rendered in flow style (`[a, b]`) to match the existing file. */
const FLOW_SEQ_KEYS = new Set([
  "roles",
  "capabilities",
  "input_types",
  "output_types",
  "values",
]);

/** Map keys rendered in flow style (`{a: 1, b: 2}`). */
const FLOW_MAP_KEYS = new Set(["cost", "limits"]);

/** YAML serializes `Date` as an ISO timestamp; we want plain `YYYY-MM-DD`. */
function flattenDates(entry: AiModel): Record<string, unknown> {
  const out: Record<string, unknown> = { ...entry };
  for (const [key, value] of Object.entries(out)) {
    if (value instanceof Date) {
      out[key] = value.toISOString().slice(0, 10);
    }
  }
  return out;
}

function parseExistingModels(yamlText: string): ExistingByProvider {
  const doc = parseDocument(yamlText);
  if (doc.contents == null) {
    return {};
  }
  if (!isMap(doc.contents)) {
    throw new Error(
      "Expected a map at the root of models.yml (keyed by provider)",
    );
  }
  const result: Record<string, ExistingEntry[]> = {};
  for (const pair of (doc.contents as YAMLMap).items) {
    const provider = (pair.key as { value?: unknown })?.value;
    if (typeof provider !== "string") {
      continue;
    }
    if (!isSeq(pair.value)) {
      result[provider] = [];
      continue;
    }
    const entries: ExistingEntry[] = [];
    for (const item of (pair.value as YAMLSeq).items) {
      if (!isMap(item)) {
        continue;
      }
      for (const subPair of (item as YAMLMap).items) {
        const key = (subPair.key as { value?: unknown })?.value;
        const value = (subPair.value as { value?: unknown })?.value;
        if (key === "model" && typeof value === "string") {
          entries.push({ model: value });
          break;
        }
      }
    }
    result[provider] = entries;
  }
  return result;
}

/**
 * Build a `YAMLMap` for one entry with the right flow-style array fields.
 */
function buildEntryNode(doc: Document, entry: AiModel): YAMLMap {
  const node = doc.createNode(flattenDates(entry)) as YAMLMap;
  formatCollections(node);
  return node;
}

function formatCollections(node: unknown): void {
  if (isSeq(node)) {
    for (const item of node.items) {
      formatCollections(item);
    }
  } else if (isMap(node)) {
    for (const pair of node.items) {
      const key = isScalar(pair.key) ? pair.key.value : undefined;
      if (typeof key !== "string") {
        continue;
      }
      if (FLOW_SEQ_KEYS.has(key) && isSeq(pair.value)) {
        pair.value.flow = true;
      } else if (FLOW_MAP_KEYS.has(key) && isMap(pair.value)) {
        pair.value.flow = true;
      }
      formatCollections(pair.value);
    }
  }
}

/**
 * Add a `provider: [...]` section to the root map, with a blank line before
 * the key when `spaceBefore` is true (used to separate provider sections).
 */
function addProviderSection(
  doc: Document,
  root: YAMLMap,
  provider: string,
  seq: YAMLSeq,
  spaceBefore: boolean,
): void {
  const keyNode = doc.createNode(provider);
  if (spaceBefore) {
    (keyNode as { spaceBefore?: boolean }).spaceBefore = true;
  }
  root.add({ key: keyNode, value: seq });
}

/**
 * Render a fresh `models.yml` from scratch (replace mode or empty bootstrap).
 */
function renderFresh(entries: ModelsByProvider): string {
  const doc = new Document({});
  const root = doc.contents as YAMLMap;
  for (const [i, [provider, models]] of Object.entries(entries).entries()) {
    const seq = doc.createNode([]) as YAMLSeq;
    for (const [j, model] of models.entries()) {
      const item = buildEntryNode(doc, model);
      if (j > 0) {
        (item as { spaceBefore?: boolean }).spaceBefore = true;
      }
      seq.items.push(item);
    }
    addProviderSection(doc, root, provider, seq, i > 0);
  }
  return doc.toString({ lineWidth: 0, flowCollectionPadding: false });
}

/**
 * Insert new entries into an existing document, creating provider sections if
 * needed, and refresh existing metadata. Preserves curated fields and comments.
 */
function updateDocument(
  yamlText: string,
  newEntries: ModelsByProvider,
  modelsDev: ModelsDevApi,
  providers: readonly string[] | undefined,
): { yaml: string; updated: number } {
  const doc = parseDocument(yamlText);
  if (doc.contents == null) {
    // Bootstrap an empty map at the root.
    doc.contents = doc.createNode({}) as unknown as typeof doc.contents;
  }
  if (!isMap(doc.contents)) {
    throw new Error(
      "Expected a map at the root of models.yml (keyed by provider)",
    );
  }
  const root = doc.contents as unknown as YAMLMap;
  const updated = refreshMetadata(doc, root, modelsDev, providers);

  for (const [provider, models] of Object.entries(newEntries)) {
    if (models.length === 0) {
      continue;
    }
    let seq = findProviderSeq(root, provider);
    if (!seq) {
      seq = doc.createNode([]) as YAMLSeq;
      // New section appended after existing content — always blank-line separated.
      addProviderSection(doc, root, provider, seq, true);
    }
    const originalFirstItem = seq.items[0] as { spaceBefore?: boolean };
    const newItems: YAMLMap[] = [];
    for (const [index, model] of models.entries()) {
      const item = buildEntryNode(doc, model);
      if (index > 0 || originalFirstItem?.spaceBefore) {
        (item as { spaceBefore?: boolean }).spaceBefore = true;
      }
      newItems.push(item);
    }
    if (newItems.length > 0 && seq.items.length > 0) {
      // Preserve a blank line between the prepended block and curated entries.
      originalFirstItem.spaceBefore = true;
    }
    seq.items.unshift(...newItems);
  }

  return {
    yaml:
      updated > 0 || Object.keys(newEntries).length > 0
        ? doc.toString({ lineWidth: 0, flowCollectionPadding: false })
        : yamlText,
    updated,
  };
}

/** Refresh only sourced metadata, preserving curation and unknown values. */
function refreshMetadata(
  doc: Document,
  root: YAMLMap,
  modelsDev: ModelsDevApi,
  providers: readonly string[] | undefined,
): number {
  let updated = 0;
  const providerFilter = providers ? new Set(providers) : null;
  for (const pair of root.items) {
    const provider = isScalar(pair.key) ? pair.key.value : undefined;
    if (typeof provider !== "string" || !isSeq(pair.value)) {
      continue;
    }
    if (providerFilter && !providerFilter.has(provider)) {
      continue;
    }
    const sourceProviders = Object.entries(PROVIDER_MAP)
      .filter(([, target]) => target === provider)
      .map(([source]) => source);
    for (const item of pair.value.items) {
      if (!isMap(item)) {
        continue;
      }
      const modelId = item.get("model");
      if (typeof modelId !== "string") {
        continue;
      }
      // Same first-source precedence as new models; no cross-provider fallback.
      const source = sourceProviders
        .map((id) => modelsDev[id]?.models[modelId])
        .find((model) => model !== undefined);
      if (!source) {
        continue;
      }
      let changed = false;
      const metadataValues = deriveMetadataUpdates(
        source,
        ExistingMetadataSchema.parse(item.toJSON()),
      );
      for (const [field, value] of Object.entries(metadataValues)) {
        const previous = item.get(field, true);
        if (JSON.stringify(previous?.toJSON()) === JSON.stringify(value)) {
          continue;
        }
        const metadata = doc.createNode({ [field]: value });
        formatCollections(metadata);
        if (!isMap(metadata)) {
          continue;
        }
        item.set(field, metadata.get(field, true));
        changed = true;
      }
      if (changed) {
        updated++;
      }
    }
  }
  return updated;
}

function findProviderSeq(root: YAMLMap, provider: string): YAMLSeq | null {
  for (const pair of root.items) {
    const key = (pair.key as { value?: unknown })?.value;
    if (key === provider && isSeq(pair.value)) {
      return pair.value;
    }
  }
  return null;
}

function countEntries(entries: ModelsByProvider): number {
  let total = 0;
  for (const list of Object.values(entries)) {
    total += list.length;
  }
  return total;
}

export async function syncModels(options: SyncOptions): Promise<SyncResult> {
  const {
    modelsYamlPath,
    write = true,
    mode = "append",
    metadataOnly = false,
    maxPerProvider,
    providers,
  } = options;
  if (metadataOnly && mode === "replace") {
    throw new Error("Metadata-only sync cannot replace the catalog");
  }
  const modelsDev = options.modelsDev ?? (await fetchModelsDev());

  // `replace` mode pretends the file is empty so everything is treated as new.
  const existingText =
    mode === "replace" ? "" : readFileSync(modelsYamlPath, "utf-8");
  const existing = parseExistingModels(existingText);
  const summary = mergeModels(existing, modelsDev, {
    maxPerProvider: metadataOnly ? 0 : maxPerProvider,
    providers,
  });

  const addedCount = countEntries(summary.newEntries);
  const isFresh = mode === "replace" || existingText.trim() === "";
  const { yaml, updated } = isFresh
    ? { yaml: renderFresh(summary.newEntries), updated: 0 }
    : updateDocument(existingText, summary.newEntries, modelsDev, providers);

  if (write && (addedCount > 0 || updated > 0 || mode === "replace")) {
    writeFileSync(modelsYamlPath, yaml);
  }

  return {
    added: addedCount,
    preserved: summary.preservedCount,
    updated,
    yaml,
  };
}

async function main(): Promise<void> {
  try {
    const dataDir = join(__dirname, "../data");
    const args = parseCliArgs(process.argv.slice(2));
    const max = args.maxPerProvider ?? MAX_MODELS_PER_PROVIDER;
    const providers = args.providers?.join(",") ?? "all";
    Logger.info(
      `Fetching models.dev catalog (mode: ${args.mode}, max-per-provider: ${max}, providers: ${providers})...`,
    );

    const result = await syncModels({
      ...args,
      modelsYamlPath: join(dataDir, "models.yml"),
    });

    Logger.info(
      `Sync complete: added ${result.added} new model(s), refreshed metadata for ${result.updated}, preserved ${result.preserved} existing entries.`,
    );
    Logger.info(
      result.added > 0 || result.updated > 0
        ? "Review the diff (git diff packages/llm-info/data/models.yml) and open a PR."
        : "No changes — models.yml is up to date.",
    );
  } catch (error) {
    Logger.error("Sync failed:", error);
    process.exit(1);
  }
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  main().catch((error) => {
    Logger.error(error);
    process.exit(1);
  });
}
