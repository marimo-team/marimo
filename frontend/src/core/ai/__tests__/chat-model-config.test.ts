/* Copyright 2026 Marimo. All rights reserved. */

import { getChatReasoningOptions } from "../reasoning-options";
import { describe, expect, it } from "vitest";
import {
  getChatModelConfig,
  getEffectiveChatOptions,
} from "../chat-model-config";
import type {
  ChatOptions,
  AiModelReasoningResponse,
} from "@/core/network/types";

function resolveModel(
  model = "openai/gpt-6-luna",
  displayed: string[] = [],
  efforts: AiModelReasoningResponse["efforts"] = [
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
  ],
) {
  const config = getChatModelConfig({
    models: {
      chat_model: model,
      custom_models: [],
      displayed_models: displayed,
    },
  });
  return {
    ...config,
    reasoningOptions: getChatReasoningOptions(config.currentModel, efforts),
  };
}

describe("chat model configuration", () => {
  it("preserves the active model when excluded from the allowlist", () => {
    const { registry, reasoningOptions, displayName } = resolveModel(
      "openai/gpt-6.1-sol",
      ["openai/gpt-6-luna"],
    );
    expect(
      registry
        .getListModelsByProvider()
        .flatMap(([, models]) => models.map((model) => model.name)),
    ).toEqual(["GPT-6.1 Sol", "GPT-6 Luna"]);
    expect(displayName).toBe("GPT-6.1 Sol");
    expect(reasoningOptions.map((option) => option.value)).toEqual([
      "default",
      "low",
      "medium",
      "high",
      "xhigh",
      "max",
    ]);
  });

  it("checks persisted effort against the current model at request time", () => {
    const options: ChatOptions & { webSearch: boolean } = {
      webSearch: true,
      reasoningEffort: "none",
    };
    expect(
      getEffectiveChatOptions(options, resolveModel().reasoningOptions),
    ).toEqual({ webSearch: true, reasoningEffort: "none" });
    expect(
      getEffectiveChatOptions(
        options,
        resolveModel("openai/gpt-6.1-sol").reasoningOptions,
      ),
    ).toEqual({ webSearch: true, reasoningEffort: null });
  });

  it("does not send efforts for unknown models", () => {
    const options: ChatOptions & { webSearch: boolean } = {
      webSearch: false,
      reasoningEffort: "high",
    };
    expect(
      getEffectiveChatOptions(
        options,
        resolveModel("openai/custom-model").reasoningOptions,
      ),
    ).toEqual({ webSearch: false, reasoningEffort: null });
  });

  it.each([
    "ollama/minimax-m3.1-flash",
    "wandb/reflection/Beam-1.0-501B-A23B",
    "opencode-go/kimi-k3.1-pro",
  ])("does not offer efforts rejected by the runtime for %s", (model) => {
    const { reasoningOptions } = resolveModel(model, [], []);
    expect(
      getEffectiveChatOptions(
        { webSearch: false, reasoningEffort: "max" },
        reasoningOptions,
      ),
    ).toEqual({ webSearch: false, reasoningEffort: null });
  });
});
