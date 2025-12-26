/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the models.json import
vi.mock("@marimo-team/llm-info/models.json", () => {
  const models: AiModel[] = [
    {
      name: "GPT-4",
      model: "gpt-4",
      description: "OpenAI GPT-4 model",
      providers: ["openai"],
      roles: ["chat", "edit"],
      thinking: false,
    },
    {
      name: "Claude 3",
      model: "claude-3-sonnet",
      description: "Anthropic Claude 3 Sonnet",
      providers: ["anthropic"],
      roles: ["chat", "edit"],
      thinking: false,
    },
    {
      name: "Gemini Pro",
      model: "gemini-pro",
      description: "Google Gemini Pro model",
      providers: ["google"],
      roles: ["chat", "edit"],
      thinking: false,
    },
    {
      name: "Multi Provider Model",
      model: "multi-model",
      description: "Model available on multiple providers",
      providers: ["openai", "anthropic"],
      roles: ["chat", "edit"],
      thinking: false,
    },
  ];

  return {
    models: models,
  };
});

import type { AiModel } from "@marimo-team/llm-info";
import { AiModelRegistry } from "../model-registry";

describe("AiModelRegistry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("create", () => {
    it("should create registry with no custom or displayed models", () => {
      const registry = AiModelRegistry.create({});

      expect(registry).toBeInstanceOf(AiModelRegistry);
      expect(registry.getCustomModels()).toEqual(new Set());
      expect(registry.getDisplayedModels()).toEqual(new Set());
    });

    it("should create registry with custom models", () => {
      const customModels = ["openai/custom-gpt", "anthropic/custom-claude"];
      const registry = AiModelRegistry.create({ customModels });

      expect(registry.getCustomModels()).toEqual(new Set(customModels));
      expect(registry.getDisplayedModels()).toEqual(new Set());

      // Expect custom models to appear first
      expect(registry.getModelsByProvider("openai")[0].name).toBe("custom-gpt");
      expect(registry.getModelsByProvider("anthropic")[0].name).toBe(
        "custom-claude",
      );
    });

    it("should create registry with displayed models", () => {
      const displayedModels = ["openai/gpt-4", "anthropic/claude-3-sonnet"];
      const registry = AiModelRegistry.create({ displayedModels });

      const ids = [...registry.getModelsMap().keys()];
      expect(ids).toEqual(["openai/gpt-4", "anthropic/claude-3-sonnet"]);
      expect(registry.getCustomModels()).toEqual(new Set());
      expect(registry.getDisplayedModels()).toEqual(new Set(displayedModels));
    });

    it("should create registry with both custom and displayed models", () => {
      const customModels = ["openai/custom-gpt"];
      const displayedModels = ["openai/custom-gpt"];
      const registry = AiModelRegistry.create({
        customModels,
        displayedModels,
      });

      const ids = [...registry.getModelsMap().keys()];
      expect(ids).toEqual(["openai/custom-gpt"]);
      expect(registry.getCustomModels()).toEqual(new Set(customModels));
      expect(registry.getDisplayedModels()).toEqual(new Set(displayedModels));
    });

    it("should create registry with non-existent displayed_model", () => {
      const customModels = ["openai/custom-gpt"];
      const displayedModels = ["something-wrong/model-id"];
      const registry = AiModelRegistry.create({
        customModels,
        displayedModels,
      });

      const ids = [...registry.getModelsMap().keys()];
      // Include custom and all default ones.
      expect(ids).toEqual([
        "openai/custom-gpt",
        "openai/gpt-4",
        "anthropic/claude-3-sonnet",
        "google/gemini-pro",
        "openai/multi-model",
        "anthropic/multi-model",
      ]);
    });
  });

  describe("getModelsByProvider", () => {
    it("should return models for a specific provider", () => {
      const registry = AiModelRegistry.create({});
      const openaiModels = registry.getModelsByProvider("openai");

      expect(openaiModels).toHaveLength(2); // gpt-4 and multi-model
      expect(
        openaiModels.every((model) => model.providers.includes("openai")),
      ).toBe(true);
    });

    it("should return empty array for provider with no models", () => {
      const registry = AiModelRegistry.create({});
      const azureModels = registry.getModelsByProvider("azure");

      expect(azureModels).toEqual([]);
    });

    it("should include custom models for the provider", () => {
      const customModels = ["openai/custom-gpt"];
      const registry = AiModelRegistry.create({ customModels });
      const openaiModels = registry.getModelsByProvider("openai");

      const customModel = openaiModels.find((model) => model.custom);
      expect(customModel).toBeDefined();
      expect(customModel?.name).toBe("custom-gpt");
      expect(customModel?.model).toBe("custom-gpt");
      expect(customModel?.description).toBe("Custom model");
      expect(customModel?.providers).toEqual(["openai"]);
      expect(customModel?.roles).toEqual([]);
      expect(customModel?.thinking).toBe(false);
    });

    it("should filter models based on displayed models", () => {
      const displayedModels = ["openai/gpt-4"];
      const registry = AiModelRegistry.create({ displayedModels });
      const openaiModels = registry.getModelsByProvider("openai");

      expect(openaiModels).toHaveLength(1);
      expect(openaiModels[0].model).toBe("gpt-4");
    });

    it("should filter custom models based on displayed models", () => {
      const customModels = ["openai/custom-gpt", "anthropic/custom-claude"];
      const displayedModels = ["openai/custom-gpt"];
      const registry = AiModelRegistry.create({
        customModels,
        displayedModels,
      });

      const openaiModels = registry.getModelsByProvider("openai");
      const anthropicModels = registry.getModelsByProvider("anthropic");

      expect(openaiModels.length).toBe(1);
      expect(openaiModels[0].name).toBe("custom-gpt");

      expect(anthropicModels.length).toBe(0);
    });
  });

  describe("getGroupedModelsByProvider", () => {
    it("should return all models grouped by provider", () => {
      const registry = AiModelRegistry.create({});
      const groupedModels = registry.getGroupedModelsByProvider();

      expect(groupedModels.has("openai")).toBe(true);
      expect(groupedModels.has("anthropic")).toBe(true);
      expect(groupedModels.has("google")).toBe(true);

      const openaiModels = groupedModels.get("openai") || [];
      const anthropicModels = groupedModels.get("anthropic") || [];
      const googleModels = groupedModels.get("google") || [];

      expect(openaiModels.length).toEqual(2);
      expect(anthropicModels.length).toEqual(2);
      expect(googleModels.length).toEqual(1);
    });

    it("should include custom models in the grouped results", () => {
      const customModels = ["openai/custom-gpt", "anthropic/custom-claude"];
      const registry = AiModelRegistry.create({ customModels });
      const groupedModels = registry.getGroupedModelsByProvider();

      const openaiModels = groupedModels.get("openai") || [];
      const anthropicModels = groupedModels.get("anthropic") || [];

      expect(
        openaiModels.some(
          (model) => model.custom && model.model === "custom-gpt",
        ),
      ).toBe(true);
      expect(
        anthropicModels.some(
          (model) => model.custom && model.model === "custom-claude",
        ),
      ).toBe(true);
    });

    it("should respect displayed models filter", () => {
      const displayedModels = ["openai/gpt-4", "anthropic/claude-3-sonnet"];
      const registry = AiModelRegistry.create({ displayedModels });
      const groupedModels = registry.getGroupedModelsByProvider();

      const openaiModels = groupedModels.get("openai") || [];
      const anthropicModels = groupedModels.get("anthropic") || [];
      const googleModels = groupedModels.get("google") || [];

      expect(openaiModels.length).toBe(1);
      expect(openaiModels[0].model).toBe("gpt-4");
      expect(anthropicModels.length).toBe(1);
      expect(anthropicModels[0].model).toBe("claude-3-sonnet");
      expect(googleModels.length).toBe(0);
    });
  });

  describe("getListModelsByProvider", () => {
    /**
     * Provider sort order depends on `provider.json`. We can hardcode for tests
     * OpenAI, Bedrock, Azure, Anthropic, Google, Ollama, GitHub, Marimo
     */
    const PROVIDER_SORT_ORDER = ["openai", "anthropic", "google"];

    it("should return list of models by provider", () => {
      const registry = AiModelRegistry.create({});
      const listModelsByProvider = registry.getListModelsByProvider();
      expect(listModelsByProvider).toHaveLength(3);

      // Should be sorted by provider
      const providers = listModelsByProvider.map(([provider]) => provider);
      expect(providers).toEqual(PROVIDER_SORT_ORDER);
    });
  });

  describe("getCustomModels", () => {
    it("should return empty set when no custom models", () => {
      const registry = AiModelRegistry.create({});
      expect(registry.getCustomModels()).toEqual(new Set());
    });

    it("should return set of custom model IDs", () => {
      const customModels = ["openai/custom-gpt", "anthropic/custom-claude"];
      const registry = AiModelRegistry.create({ customModels });
      expect(registry.getCustomModels()).toEqual(new Set(customModels));
    });
  });

  describe("getDisplayedModels", () => {
    it("should return empty set when no displayed models specified", () => {
      const registry = AiModelRegistry.create({});
      expect(registry.getDisplayedModels()).toEqual(new Set());
    });

    it("should return set of displayed model IDs", () => {
      const displayedModels = ["openai/gpt-4", "anthropic/claude-3-sonnet"];
      const registry = AiModelRegistry.create({ displayedModels });
      expect(registry.getDisplayedModels()).toEqual(new Set(displayedModels));
    });
  });

  describe("edge cases", () => {
    it("should handle empty arrays for custom and displayed models", () => {
      const registry = AiModelRegistry.create({
        customModels: [],
        displayedModels: [],
      });

      expect(registry.getCustomModels()).toEqual(new Set());
      expect(registry.getDisplayedModels()).toEqual(new Set());

      // Should still load default models
      const openaiModels = registry.getModelsByProvider("openai");
      expect(openaiModels.length).toBeGreaterThan(0);
    });

    it("should handle models with multiple providers", () => {
      const registry = AiModelRegistry.create({});

      const openaiModels = registry.getModelsByProvider("openai");
      const anthropicModels = registry.getModelsByProvider("anthropic");

      // The multi-model should appear in both providers
      const multiModelInOpenai = openaiModels.find(
        (model) => model.model === "multi-model",
      );
      const multiModelInAnthropic = anthropicModels.find(
        (model) => model.model === "multi-model",
      );

      expect(multiModelInOpenai).toBeDefined();
      expect(multiModelInAnthropic).toBeDefined();
      expect(multiModelInOpenai).toEqual(multiModelInAnthropic);
    });

    it("should handle displayed models filter with non-existent models", () => {
      const displayedModels = [
        "openai/non-existent-model",
        "anthropic/claude-3-sonnet",
      ];
      const registry = AiModelRegistry.create({ displayedModels });

      const openaiModels = registry.getModelsByProvider("openai");
      const anthropicModels = registry.getModelsByProvider("anthropic");

      // Should only show the existing model
      expect(openaiModels.length).toBe(0);
      expect(anthropicModels.length).toBe(1);
      expect(anthropicModels[0].model).toBe("claude-3-sonnet");
    });
  });

  describe("model properties", () => {
    it("should ensure all models have required properties", () => {
      const registry = AiModelRegistry.create({});
      const groupedModels = registry.getGroupedModelsByProvider();

      for (const [provider, models] of groupedModels.entries()) {
        for (const model of models) {
          expect(model).toHaveProperty("name");
          expect(model).toHaveProperty("model");
          expect(model).toHaveProperty("description");
          expect(model).toHaveProperty("providers");
          expect(model).toHaveProperty("roles");
          expect(model).toHaveProperty("thinking");
          expect(model).toHaveProperty("custom");

          expect(typeof model.name).toBe("string");
          expect(typeof model.model).toBe("string");
          expect(typeof model.description).toBe("string");
          expect(Array.isArray(model.providers)).toBe(true);
          expect(Array.isArray(model.roles)).toBe(true);
          expect(typeof model.thinking).toBe("boolean");
          expect(typeof model.custom).toBe("boolean");

          expect(model.providers).toContain(provider);
        }
      }
    });

    it("should ensure custom models have correct custom property", () => {
      const customModels = ["openai/custom-gpt"];
      const registry = AiModelRegistry.create({ customModels });
      const openaiModels = registry.getModelsByProvider("openai");

      const customModel = openaiModels.find((model) => model.custom);
      const defaultModel = openaiModels.find((model) => !model.custom);

      expect(customModel).toMatchInlineSnapshot(`
        {
          "custom": true,
          "description": "Custom model",
          "model": "custom-gpt",
          "name": "custom-gpt",
          "providers": [
            "openai",
          ],
          "roles": [],
          "thinking": false,
        }
      `);
      expect(defaultModel).toMatchInlineSnapshot(`
        {
          "custom": false,
          "description": "OpenAI GPT-4 model",
          "model": "gpt-4",
          "name": "GPT-4",
          "providers": [
            "openai",
          ],
          "roles": [
            "chat",
            "edit",
          ],
          "thinking": false,
        }
      `);
    });
  });
});
