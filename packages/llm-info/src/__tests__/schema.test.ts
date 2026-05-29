import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import {
  LLMInfoSchema,
  ModelsByProviderSchema,
  ProviderSchema,
} from "../generate";

describe("LLMInfoSchema", () => {
  it("validates a complete model entry", () => {
    const validModel = {
      name: "Test Model",
      model: "test-model-v1",
      description: "A test model for validation",
      roles: ["chat", "edit"],
      capabilities: ["thinking", "tool_calling"],
      input_types: ["text", "image"],
      output_types: ["text"],
      release_date: "2026-01-15",
    };

    expect(LLMInfoSchema.parse(validModel)).toEqual(validModel);
  });

  it("defaults capabilities / input_types / output_types to empty arrays", () => {
    const minimal = {
      name: "Test Model",
      model: "test-model-v1",
      description: "A test model",
      roles: ["chat"],
    };

    const parsed = LLMInfoSchema.parse(minimal);
    expect(parsed.capabilities).toEqual([]);
    expect(parsed.input_types).toEqual([]);
    expect(parsed.output_types).toEqual([]);
  });

  it("rejects unknown roles", () => {
    const invalidModel = {
      name: "Test Model",
      model: "test-model-v1",
      description: "A test model",
      roles: ["invalid-role"],
    };

    expect(() => LLMInfoSchema.parse(invalidModel)).toThrow();
  });

  it("requires the core identity fields", () => {
    expect(() =>
      LLMInfoSchema.parse({ name: "Test Model", model: "test-model-v1" }),
    ).toThrow();
  });
});

describe("ProviderSchema", () => {
  it("validates a valid provider object", () => {
    const validProvider = {
      name: "Test Provider",
      id: "test-provider",
      description: "A test provider for validation",
      url: "https://example.com",
    };

    expect(ProviderSchema.parse(validProvider)).toEqual(validProvider);
  });

  it("rejects invalid URLs", () => {
    expect(() =>
      ProviderSchema.parse({
        name: "Test Provider",
        id: "test-provider",
        description: "A test provider",
        url: "not-a-valid-url",
      }),
    ).toThrow();
  });

  it("requires all fields", () => {
    expect(() =>
      ProviderSchema.parse({ name: "Test Provider", id: "test-provider" }),
    ).toThrow();
  });
});

describe("Data Validation", () => {
  it("validates the structure of data/models.yml as a provider-keyed map", () => {
    const modelsPath = join(__dirname, "../../data/models.yml");
    const modelsYaml = readFileSync(modelsPath, "utf-8");
    const data = parse(modelsYaml);

    expect(typeof data).toBe("object");
    expect(Array.isArray(data)).toBe(false);
    expect(() => ModelsByProviderSchema.parse(data)).not.toThrow();
  });
});
