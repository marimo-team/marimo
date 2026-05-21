/* Copyright 2026 Marimo. All rights reserved. */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { z } from "zod";
import { Logger } from "../simple_logger.ts";

export const ModelsDevModelSchema = z.object({
  id: z.string(),
  name: z.string(),
  reasoning: z.boolean().optional(),
  tool_call: z.boolean().optional(),
  release_date: z.string().optional(),
  modalities: z
    .object({
      input: z.array(z.string()).optional(),
      output: z.array(z.string()).optional(),
    })
    .optional(),
  limit: z
    .object({
      context: z.number().optional(),
      output: z.number().optional(),
    })
    .optional(),
  cost: z
    .object({
      input: z.number().optional(),
      output: z.number().optional(),
    })
    .partial()
    .optional(),
});

export type ModelsDevModel = z.infer<typeof ModelsDevModelSchema>;

export interface ModelsDevProvider {
  id: string;
  name?: string;
  models: Record<string, ModelsDevModel>;
}

export type ModelsDevApi = Record<string, ModelsDevProvider>;

const DEFAULT_URL = "https://models.dev/api.json";

export function parseModelsDev(raw: unknown): ModelsDevApi {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    throw new Error("models.dev response is not an object");
  }

  const out: ModelsDevApi = {};
  let skippedModels = 0;

  for (const [providerId, providerRaw] of Object.entries(
    raw as Record<string, unknown>,
  )) {
    if (
      typeof providerRaw !== "object" ||
      providerRaw === null ||
      Array.isArray(providerRaw)
    ) {
      Logger.warn(
        `models.dev: skipping provider "${providerId}" (not an object)`,
      );
      continue;
    }
    const providerObj = providerRaw as {
      id?: unknown;
      name?: unknown;
      models?: unknown;
    };
    if (
      typeof providerObj.models !== "object" ||
      providerObj.models === null ||
      Array.isArray(providerObj.models)
    ) {
      Logger.warn(`models.dev: skipping provider "${providerId}" (no models)`);
      continue;
    }

    const models: Record<string, ModelsDevModel> = {};
    for (const [modelId, modelRaw] of Object.entries(
      providerObj.models as Record<string, unknown>,
    )) {
      const parsed = ModelsDevModelSchema.safeParse(modelRaw);
      if (parsed.success) {
        models[modelId] = parsed.data;
      } else {
        skippedModels += 1;
        Logger.warn(
          `models.dev: skipping ${providerId}/${modelId} (${parsed.error.issues[0]?.message ?? "validation error"})`,
        );
      }
    }

    out[providerId] = {
      id: typeof providerObj.id === "string" ? providerObj.id : providerId,
      name: typeof providerObj.name === "string" ? providerObj.name : undefined,
      models,
    };
  }

  if (skippedModels > 0) {
    Logger.warn(
      `models.dev: skipped ${skippedModels} malformed model(s) total`,
    );
  }

  return out;
}

export interface FetchModelsDevOptions {
  url?: string;
  /**
   * When set, the raw `api.json` response is written verbatim to this path
   * before being parsed. Useful as a debugging snapshot or fallback source.
   */
  snapshotPath?: string;
}

export async function fetchModelsDev(
  options: FetchModelsDevOptions = {},
): Promise<ModelsDevApi> {
  const { url = DEFAULT_URL, snapshotPath } = options;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${url}: ${response.status} ${response.statusText}`,
    );
  }
  const json = (await response.json()) as unknown;
  if (snapshotPath) {
    try {
      mkdirSync(dirname(snapshotPath), { recursive: true });
      writeFileSync(snapshotPath, `${JSON.stringify(json, null, 2)}\n`);
    } catch (error) {
      Logger.warn(
        `Failed to write models.dev snapshot to ${snapshotPath}:`,
        error,
      );
    }
  }
  return parseModelsDev(json);
}
