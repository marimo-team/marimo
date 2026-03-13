#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { z } from "zod";
import { Logger } from "./simple_logger.ts";

const ROLES = ["chat", "edit", "rerank", "embed"] as const;

export const LLMInfoSchema = z.object({
  name: z.string(),
  model: z.string(),
  description: z.string(),
  providers: z.array(z.string()),
  roles: z.array(z.enum(ROLES)),
  thinking: z.boolean().default(false),
});

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
    // Ignore error if directory already exists, otherwise rethrow
    if (error?.code !== "EEXIST") {
      Logger.error("Failed to create directory:", error);
      throw error;
    }
  }
}

function loadAndValidateModels(yamlPath: string): any[] {
  const yamlContent = readFileSync(yamlPath, "utf-8");
  const models = parse(yamlContent);

  if (!Array.isArray(models)) {
    throw new Error("Models YAML file must contain an array");
  }

  // Validate each model against the schema
  const validatedModels = models.map((model, index) => {
    try {
      return LLMInfoSchema.parse(model);
    } catch (error) {
      Logger.error(`Validation failed for model at index ${index}:`, error);
      throw new Error(
        `Model validation failed at index ${index}: ${JSON.stringify(model, null, 2)}`,
      );
    }
  });

  return validatedModels;
}

function loadAndValidateProviders(yamlPath: string): any[] {
  const yamlContent = readFileSync(yamlPath, "utf-8");
  const providers = parse(yamlContent);

  if (!Array.isArray(providers)) {
    throw new Error("Providers YAML file must contain an array");
  }

  // Validate each provider against the schema
  const validatedProviders = providers.map((provider, index) => {
    try {
      return ProviderSchema.parse(provider);
    } catch (error) {
      Logger.error(`Validation failed for provider at index ${index}:`, error);
      throw new Error(
        `Provider validation failed at index ${index}: ${JSON.stringify(provider, null, 2)}`,
      );
    }
  });

  return validatedProviders;
}

function writeJsonFile(filePath: string, data: any): void {
  ensureDirectoryExists(filePath);
  writeFileSync(filePath, JSON.stringify(data, null, 2));
}

async function main(): Promise<void> {
  try {
    // Define paths
    const dataDir = join(__dirname, "../data");
    const generatedDir = join(dataDir, "generated");
    const modelsYamlPath = join(dataDir, "models.yml");
    const providersYamlPath = join(dataDir, "providers.yml");
    const modelsJsonPath = join(generatedDir, "models.json");
    const providersJsonPath = join(generatedDir, "providers.json");

    // For compatibility with Vite and other bundlers, `import` returns a JS module and not a JSON object.
    // So we need to nest the models and providers data under a json key to access them,
    // otherwise a keyword can conflict with a JS reserved keyword (e.g. `default` or `with`).

    // Load and validate models
    const models = loadAndValidateModels(modelsYamlPath);
    writeJsonFile(modelsJsonPath, { models: models });

    // Load and validate providers
    const providers = loadAndValidateProviders(providersYamlPath);
    writeJsonFile(providersJsonPath, { providers: providers });

    Logger.info(
      `Generated ${models.length} models and ${providers.length} providers`,
    );
  } catch (error) {
    Logger.error("Generation failed:", error);
    process.exit(1);
  }
}

// Run the script
main().catch(Logger.error);
