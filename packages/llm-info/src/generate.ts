#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { z } from "zod";
import { Logger } from "./simple_logger.ts";

const ROLES = ["chat", "edit", "rerank", "embed", "autocomplete"] as const;
const CAPABILITIES = ["thinking", "tool_calling"] as const;
const DATA_TYPES = ["text", "image", "pdf"] as const;

const CostSchema = z
  .object({
    input: z.number().optional(),
    output: z.number().optional(),
  })
  .partial();

/** YAML may parse `YYYY-MM-DD` scalars as Date; coerce back to ISO string. */
const ReleaseDateSchema = z
  .union([z.string(), z.date()])
  .optional()
  .transform((v) => {
    if (v === undefined) return undefined;
    if (v instanceof Date) return v.toISOString().slice(0, 10);
    return v;
  });

export const LLMInfoSchema = z.object({
  name: z.string(),
  model: z.string(),
  description: z.string(),
  roles: z.array(z.enum(ROLES)),
  capabilities: z.array(z.enum(CAPABILITIES)).default([]),
  input_types: z.array(z.enum(DATA_TYPES)).default([]),
  output_types: z.array(z.enum(DATA_TYPES)).default([]),
  release_date: ReleaseDateSchema,
  cost: CostSchema.optional(),
});

/** Top-level shape of `models.yml` / `models.json`: provider id → models. */
export const ModelsByProviderSchema = z.record(
  z.string(),
  z.array(LLMInfoSchema),
);

export const ProviderSchema = z.object({
  name: z.string(),
  id: z.string(),
  description: z.string(),
  url: z.string().url(),
});

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function ensureDirectoryExists(filePath: string): void {
  const dir = dirname(filePath);
  try {
    mkdirSync(dir, { recursive: true });
  } catch (error: any) {
    if (error?.code !== "EEXIST") {
      Logger.error("Failed to create directory:", error);
      throw error;
    }
  }
}

function loadAndValidateModels(yamlPath: string): Record<string, unknown[]> {
  const yamlContent = readFileSync(yamlPath, "utf-8");
  const raw = parse(yamlContent);

  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error(
      "Models YAML must be a map keyed by provider id (e.g. `anthropic:`)",
    );
  }

  try {
    return ModelsByProviderSchema.parse(raw);
  } catch (error) {
    Logger.error("Model validation failed:", error);
    throw error;
  }
}

function loadAndValidateProviders(yamlPath: string): unknown[] {
  const yamlContent = readFileSync(yamlPath, "utf-8");
  const providers = parse(yamlContent);

  if (!Array.isArray(providers)) {
    throw new Error("Providers YAML file must contain an array");
  }

  return providers.map((provider, index) => {
    try {
      return ProviderSchema.parse(provider);
    } catch (error) {
      Logger.error(`Validation failed for provider at index ${index}:`, error);
      throw new Error(
        `Provider validation failed at index ${index}: ${JSON.stringify(provider, null, 2)}`,
      );
    }
  });
}

function writeJsonFile(filePath: string, data: unknown): void {
  ensureDirectoryExists(filePath);
  writeFileSync(filePath, JSON.stringify(data, null, 2));
}

async function main(): Promise<void> {
  try {
    const dataDir = join(__dirname, "../data");
    const generatedDir = join(dataDir, "generated");
    const modelsYamlPath = join(dataDir, "models.yml");
    const providersYamlPath = join(dataDir, "providers.yml");
    const modelsJsonPath = join(generatedDir, "models.json");
    const providersJsonPath = join(generatedDir, "providers.json");

    const models = loadAndValidateModels(modelsYamlPath);
    writeJsonFile(modelsJsonPath, { models });

    const providers = loadAndValidateProviders(providersYamlPath);
    writeJsonFile(providersJsonPath, { providers });

    const totalModels = Object.values(models).reduce(
      (acc, list) => acc + list.length,
      0,
    );
    Logger.info(
      `Generated ${totalModels} models across ${Object.keys(models).length} providers and ${providers.length} provider entries`,
    );
  } catch (error) {
    Logger.error("Generation failed:", error);
    process.exit(1);
  }
}

main().catch(Logger.error);
