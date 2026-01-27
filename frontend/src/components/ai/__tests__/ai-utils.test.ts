/* Copyright 2026 Marimo. All rights reserved. */

import type { AiModel } from "@marimo-team/llm-info";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserConfig } from "@/core/config/config-schema";

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
      name: "Ollama Model",
      model: "llama2",
      description: "Ollama Llama 2 model",
      providers: ["ollama"],
      roles: ["chat", "edit"],
      thinking: false,
    },
  ];

  return {
    models: models,
  };
});

// Must import after mock
import {
  autoPopulateModels,
  getConfiguredProvider,
  getRecommendedModel,
} from "../ai-utils";

describe("ai-utils", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getConfiguredProvider", () => {
    it("should return undefined when no AI config", () => {
      const config: UserConfig = {} as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBeUndefined();
    });

    it("should return undefined when AI config has no credentials", () => {
      const config: UserConfig = {
        ai: {},
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBeUndefined();
    });

    it("should return openai when OpenAI API key is set", () => {
      const config: UserConfig = {
        ai: {
          open_ai: { api_key: "sk-test" },
        },
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBe("openai");
    });

    it("should return anthropic when Anthropic API key is set", () => {
      const config: UserConfig = {
        ai: {
          anthropic: { api_key: "sk-ant-test" },
        },
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBe("anthropic");
    });

    it("should return google when Google API key is set", () => {
      const config: UserConfig = {
        ai: {
          google: { api_key: "google-key" },
        },
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBe("google");
    });

    it("should return ollama when Ollama base URL is set", () => {
      const config: UserConfig = {
        ai: {
          ollama: { base_url: "http://localhost:11434" },
        },
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBe("ollama");
    });

    it("should return azure only when both API key and base URL are set", () => {
      const config: UserConfig = {
        ai: {
          azure: { api_key: "azure-key", base_url: "https://azure.com" },
        },
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBe("azure");
    });

    it("should return undefined for azure with only API key", () => {
      const config: UserConfig = {
        ai: {
          azure: { api_key: "azure-key" },
        },
      } as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBeUndefined();
    });

    it("should return custom provider when configured", () => {
      const config = {
        ai: {
          custom_providers: {
            my_provider: { base_url: "https://my-api.com" },
          },
        },
      } as unknown as UserConfig;
      expect(getConfiguredProvider(config.ai)).toBe("my_provider");
    });
  });

  describe("getRecommendedModel", () => {
    it("should return undefined when no provider is configured", () => {
      const config: UserConfig = {} as UserConfig;
      expect(getRecommendedModel(config.ai)).toBeUndefined();
    });

    it("should return openai model when OpenAI is configured", () => {
      const config: UserConfig = {
        ai: {
          open_ai: { api_key: "sk-test" },
        },
      } as UserConfig;
      expect(getRecommendedModel(config.ai)).toBe("openai/gpt-4");
    });

    it("should return anthropic model when Anthropic is configured", () => {
      const config: UserConfig = {
        ai: {
          anthropic: { api_key: "sk-ant-test" },
        },
      } as UserConfig;
      expect(getRecommendedModel(config.ai)).toBe("anthropic/claude-3-sonnet");
    });

    it("should return google model when Google is configured", () => {
      const config: UserConfig = {
        ai: {
          google: { api_key: "google-key" },
        },
      } as UserConfig;
      expect(getRecommendedModel(config.ai)).toBe("google/gemini-pro");
    });

    it("should return ollama model when Ollama is configured", () => {
      const config: UserConfig = {
        ai: {
          ollama: { base_url: "http://localhost:11434" },
        },
      } as UserConfig;
      expect(getRecommendedModel(config.ai)).toBe("ollama/llama2");
    });
  });

  describe("autoPopulateModels", () => {
    it("should return empty result when both models are already set", () => {
      const values = {
        ai: {
          open_ai: { api_key: "sk-test" },
          models: {
            chat_model: "openai/gpt-4",
            edit_model: "openai/gpt-4",
            custom_models: [],
            displayed_models: [],
          },
        },
      } as unknown as UserConfig;

      const result = autoPopulateModels(values.ai);

      expect(result.chatModel).toBeUndefined();
      expect(result.editModel).toBeUndefined();
    });

    it("should return empty result when no credentials are configured", () => {
      const values: UserConfig = {
        ai: {},
      } as UserConfig;

      const result = autoPopulateModels(values.ai);

      expect(result.chatModel).toBeUndefined();
      expect(result.editModel).toBeUndefined();
    });

    it("should auto-populate both models when neither is set", () => {
      const values: UserConfig = {
        ai: {
          open_ai: { api_key: "sk-test" },
        },
      } as UserConfig;

      const result = autoPopulateModels(values.ai);

      expect(result.chatModel).toBe("openai/gpt-4");
      expect(result.editModel).toBe("openai/gpt-4");
    });

    it("should only auto-populate chat_model when edit_model is set", () => {
      const values = {
        ai: {
          open_ai: { api_key: "sk-test" },
          models: {
            edit_model: "openai/gpt-3.5-turbo",
            custom_models: [],
            displayed_models: [],
          },
        },
      } as unknown as UserConfig;

      const result = autoPopulateModels(values.ai);

      expect(result.chatModel).toBe("openai/gpt-4");
      expect(result.editModel).toBeUndefined();
    });

    it("should only auto-populate edit_model when chat_model is set", () => {
      const values = {
        ai: {
          open_ai: { api_key: "sk-test" },
          models: {
            chat_model: "openai/gpt-3.5-turbo",
            custom_models: [],
            displayed_models: [],
          },
        },
      } as unknown as UserConfig;

      const result = autoPopulateModels(values.ai);

      expect(result.chatModel).toBeUndefined();
      expect(result.editModel).toBe("openai/gpt-4");
    });

    it("should return recommended model for anthropic provider", () => {
      const values: UserConfig = {
        ai: {
          anthropic: { api_key: "sk-ant-test" },
        },
      } as UserConfig;

      const result = autoPopulateModels(values.ai);

      expect(result.chatModel).toBe("anthropic/claude-3-sonnet");
      expect(result.editModel).toBe("anthropic/claude-3-sonnet");
    });
  });
});
