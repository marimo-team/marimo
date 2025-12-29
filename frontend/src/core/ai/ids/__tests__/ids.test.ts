/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { ProviderId } from "../ids";
import { AiModelId, type ShortModelId } from "../ids";

describe("AiModelId", () => {
  describe("constructor", () => {
    it("should create an instance with providerId and shortModelId", () => {
      const modelId = new AiModelId("openai", "gpt-4" as ShortModelId);
      expect(modelId.providerId).toBe("openai");
      expect(modelId.shortModelId).toBe("gpt-4");
    });
  });

  describe("id getter", () => {
    it("should return qualified model id", () => {
      const modelId = new AiModelId("anthropic", "claude-3" as ShortModelId);
      expect(modelId.id).toBe("anthropic/claude-3");
    });

    it("should handle all provider types", () => {
      const providers: ProviderId[] = [
        "openai",
        "anthropic",
        "google",
        "ollama",
        "bedrock",
        "github",
      ];

      providers.forEach((provider) => {
        const modelId = new AiModelId(provider, "test-model" as ShortModelId);
        expect(modelId.id).toBe(`${provider}/test-model`);
      });
    });
  });

  describe("parse", () => {
    describe("with qualified ids (containing '/')", () => {
      it("should parse openai qualified id", () => {
        const modelId = AiModelId.parse("openai/gpt-4");
        expect(modelId.providerId).toBe("openai");
        expect(modelId.shortModelId).toBe("gpt-4");
      });

      it("should parse anthropic qualified id", () => {
        const modelId = AiModelId.parse("anthropic/claude-3-sonnet");
        expect(modelId.providerId).toBe("anthropic");
        expect(modelId.shortModelId).toBe("claude-3-sonnet");
      });

      it("should parse google qualified id", () => {
        const modelId = AiModelId.parse("google/gemini-pro");
        expect(modelId.providerId).toBe("google");
        expect(modelId.shortModelId).toBe("gemini-pro");
      });

      it("should parse ollama qualified id", () => {
        const modelId = AiModelId.parse("ollama/llama2");
        expect(modelId.providerId).toBe("ollama");
        expect(modelId.shortModelId).toBe("llama2");
      });

      it("should parse bedrock qualified id", () => {
        const modelId = AiModelId.parse("bedrock/titan-text");
        expect(modelId.providerId).toBe("bedrock");
        expect(modelId.shortModelId).toBe("titan-text");
      });

      it("should parse github qualified id", () => {
        const modelId = AiModelId.parse("github/gpt-4o");
        expect(modelId.providerId).toBe("github");
        expect(modelId.shortModelId).toBe("gpt-4o");
      });

      it("should handle multiple slashes", () => {
        const modelId = AiModelId.parse("openai/gpt-4/turbo");
        expect(modelId.providerId).toBe("openai");
        expect(modelId.shortModelId).toBe("gpt-4/turbo");
      });
    });

    describe("without qualified ids (no '/')", () => {
      describe("openai models", () => {
        it("should guess openai for gpt models", () => {
          const modelId = AiModelId.parse("gpt-4");
          expect(modelId.providerId).toBe("openai");
          expect(modelId.shortModelId).toBe("gpt-4");
        });

        it("should guess openai for gpt-3.5 models", () => {
          const modelId = AiModelId.parse("gpt-3.5-turbo");
          expect(modelId.providerId).toBe("openai");
          expect(modelId.shortModelId).toBe("gpt-3.5-turbo");
        });

        it("should guess openai for o3 models", () => {
          const modelId = AiModelId.parse("o3-mini");
          expect(modelId.providerId).toBe("openai");
          expect(modelId.shortModelId).toBe("o3-mini");
        });

        it("should guess openai for o1 models", () => {
          const modelId = AiModelId.parse("o1-preview");
          expect(modelId.providerId).toBe("openai");
          expect(modelId.shortModelId).toBe("o1-preview");
        });
      });

      describe("anthropic models", () => {
        it("should guess anthropic for claude models", () => {
          const modelId = AiModelId.parse("claude-3-sonnet");
          expect(modelId.providerId).toBe("anthropic");
          expect(modelId.shortModelId).toBe("claude-3-sonnet");
        });

        it("should guess anthropic for claude-instant", () => {
          const modelId = AiModelId.parse("claude-instant");
          expect(modelId.providerId).toBe("anthropic");
          expect(modelId.shortModelId).toBe("claude-instant");
        });
      });

      describe("google models", () => {
        it("should guess google for gemini models", () => {
          const modelId = AiModelId.parse("gemini-pro");
          expect(modelId.providerId).toBe("google");
          expect(modelId.shortModelId).toBe("gemini-pro");
        });

        it("should guess google for google-prefixed models", () => {
          const modelId = AiModelId.parse("google-palm");
          expect(modelId.providerId).toBe("google");
          expect(modelId.shortModelId).toBe("google-palm");
        });
      });

      describe("ollama fallback", () => {
        it("should default to ollama for unknown models", () => {
          const modelId = AiModelId.parse("llama2");
          expect(modelId.providerId).toBe("ollama");
          expect(modelId.shortModelId).toBe("llama2");
        });

        it("should default to ollama for custom models", () => {
          const modelId = AiModelId.parse("my-custom-model");
          expect(modelId.providerId).toBe("ollama");
          expect(modelId.shortModelId).toBe("my-custom-model");
        });

        it("should default to ollama for empty string", () => {
          const modelId = AiModelId.parse("");
          expect(modelId.providerId).toBe("ollama");
          expect(modelId.shortModelId).toBe("");
        });
      });
    });
  });

  describe("round-trip parsing", () => {
    it("should maintain consistency when parsing generated ids", () => {
      const original = new AiModelId(
        "anthropic",
        "claude-3-opus" as ShortModelId,
      );
      const parsed = AiModelId.parse(original.id);

      expect(parsed.providerId).toBe(original.providerId);
      expect(parsed.shortModelId).toBe(original.shortModelId);
      expect(parsed.id).toBe(original.id);
    });

    it("should work for all providers", () => {
      const providers: ProviderId[] = [
        "openai",
        "anthropic",
        "google",
        "ollama",
        "bedrock",
        "github",
      ];

      providers.forEach((provider) => {
        const original = new AiModelId(provider, "test-model" as ShortModelId);
        const parsed = AiModelId.parse(original.id);

        expect(parsed.providerId).toBe(provider);
        expect(parsed.shortModelId).toBe("test-model");
      });
    });
  });
});
