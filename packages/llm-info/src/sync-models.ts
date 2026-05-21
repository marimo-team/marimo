#!/usr/bin/env node
/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  Document,
  isMap,
  isSeq,
  parseDocument,
  type YAMLMap,
  type YAMLSeq,
} from "yaml";
import { parseCliArgs } from "./cli.ts";
import type { AiModel, ModelsByProvider } from "./index.ts";
import { Logger } from "./simple_logger.ts";
import {
  type ExistingByProvider,
  type ExistingEntry,
  MAX_MODELS_PER_PROVIDER,
  mergeModels,
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
  /** Cap on new entries appended per provider section. */
  maxPerProvider?: number;
  /** Restrict sync to these marimo provider ids (defaults to all). */
  providers?: readonly string[];
}

export interface SyncResult {
  added: number;
  preserved: number;
  yaml: string;
}

/** Sequence keys rendered in flow style (`[a, b]`) to match the existing file. */
const FLOW_SEQ_KEYS = new Set([
  "roles",
  "capabilities",
  "input_types",
  "output_types",
]);

/** Map keys rendered in flow style (`{a: 1, b: 2}`). */
const FLOW_MAP_KEYS = new Set(["cost"]);

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
  for (const pair of node.items) {
    const key = (pair.key as { value?: unknown })?.value;
    if (typeof key !== "string") {
      continue;
    }
    if (FLOW_SEQ_KEYS.has(key) && isSeq(pair.value)) {
      pair.value.flow = true;
    } else if (FLOW_MAP_KEYS.has(key) && isMap(pair.value)) {
      pair.value.flow = true;
    }
  }
  return node;
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
 * Append new entries into an existing document, creating provider sections if
 * needed. Preserves comments and ordering of unchanged sections.
 */
function appendIntoDocument(
  yamlText: string,
  newEntries: ModelsByProvider,
): string {
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
    for (const model of models) {
      const item = buildEntryNode(doc, model);
      if (seq.items.length > 0) {
        (item as { spaceBefore?: boolean }).spaceBefore = true;
      }
      seq.items.push(item);
    }
  }

  return doc.toString({ lineWidth: 0, flowCollectionPadding: false });
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
    maxPerProvider,
    providers,
  } = options;
  const modelsDev = options.modelsDev ?? (await fetchModelsDev());

  // `replace` mode pretends the file is empty so everything is treated as new.
  const existingText =
    mode === "replace" ? "" : readFileSync(modelsYamlPath, "utf-8");
  const existing = parseExistingModels(existingText);
  const summary = mergeModels(existing, modelsDev, {
    maxPerProvider,
    providers,
  });

  const addedCount = countEntries(summary.newEntries);
  const isFresh = mode === "replace" || existingText.trim() === "";
  const yaml = isFresh
    ? renderFresh(summary.newEntries)
    : addedCount > 0
      ? appendIntoDocument(existingText, summary.newEntries)
      : existingText;

  if (write && (addedCount > 0 || mode === "replace")) {
    writeFileSync(modelsYamlPath, yaml);
  }

  return {
    added: addedCount,
    preserved: summary.preservedCount,
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
      `Sync complete: added ${result.added} new model(s), preserved ${result.preserved} existing entries.`,
    );
    Logger.info(
      result.added > 0
        ? "Review the diff (git diff packages/llm-info/data/models.yml) and open a PR."
        : "No changes — models.yml is up to date.",
    );
  } catch (error) {
    Logger.error("Sync failed:", error);
    process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    Logger.error(error);
    process.exit(1);
  });
}
