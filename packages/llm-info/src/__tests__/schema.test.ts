import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { LLMInfoSchema, ProviderSchema } from "../generate";

describe("LLMInfoSchema", () => {
  it("should validate a valid LLM info object", () => {
    const validModel = {
      name: "Test Model",
      model: "test-model-v1",
      description: "A test model for validation",
      providers: ["test-provider"],
      roles: ["chat", "edit"],
      thinking: true,
    };

    expect(() => LLMInfoSchema.parse(validModel)).not.toThrow();
    const result = LLMInfoSchema.parse(validModel);
    expect(result).toEqual(validModel);
  });

  it("should set thinking to false by default", () => {
    const modelWithoutThinking = {
      name: "Test Model",
      model: "test-model-v1",
      description: "A test model for validation",
      providers: ["test-provider"],
      roles: ["chat"],
    };

    const result = LLMInfoSchema.parse(modelWithoutThinking);
    expect(result.thinking).toBe(false);
  });

  it("should reject invalid roles", () => {
    const invalidModel = {
      name: "Test Model",
      model: "test-model-v1",
      description: "A test model for validation",
      providers: ["test-provider"],
      roles: ["invalid-role"],
      thinking: false,
    };

    expect(() => LLMInfoSchema.parse(invalidModel)).toThrow();
  });

  it("should require all mandatory fields", () => {
    const incompleteModel = {
      name: "Test Model",
      model: "test-model-v1",
    };

    expect(() => LLMInfoSchema.parse(incompleteModel)).toThrow();
  });
});

describe("ProviderSchema", () => {
  it("should validate a valid provider object", () => {
    const validProvider = {
      name: "Test Provider",
      id: "test-provider",
      description: "A test provider for validation",
      url: "https://example.com",
    };

    expect(() => ProviderSchema.parse(validProvider)).not.toThrow();
    const result = ProviderSchema.parse(validProvider);
    expect(result).toEqual(validProvider);
  });

  it("should reject invalid URLs", () => {
    const invalidProvider = {
      name: "Test Provider",
      id: "test-provider",
      description: "A test provider for validation",
      url: "not-a-valid-url",
    };

    expect(() => ProviderSchema.parse(invalidProvider)).toThrow();
  });

  it("should require all fields", () => {
    const incompleteProvider = {
      name: "Test Provider",
      id: "test-provider",
    };

    expect(() => ProviderSchema.parse(incompleteProvider)).toThrow();
  });
});

describe("Data Validation", () => {
  it("should validate all models in data/models.yml", () => {
    const modelsPath = join(__dirname, "../../data/models.yml");
    const modelsYaml = readFileSync(modelsPath, "utf-8");
    const models = parse(modelsYaml);

    expect(Array.isArray(models)).toBe(true);
    expect(models.length).toBeGreaterThan(0);

    models.forEach((model: any, index: number) => {
      expect(() => LLMInfoSchema.parse(model)).not.toThrow(
        `Model at index ${index} failed validation: ${JSON.stringify(model)}`,
      );
    });
  });
});
