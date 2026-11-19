/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  getChatModelConfig,
  getChatModelId,
  getEffectiveChatOptions,
} from "../chat-model-config";
import type { ChatOptions } from "@/core/network/types";
import { defaultUserConfig } from "@/core/config/config-schema";

function resolveModel(model = "openai/gpt-6-luna", displayed: string[] = []) {
  const ai = defaultUserConfig().ai;
  return getChatModelConfig({
    ...ai,
    models: {
      ...ai.models,
      chat_model: model,
      custom_models: [],
      displayed_models: displayed,
    },
  });
}

describe("chat model configuration", () => {
  it.each([
    ["o4-mini", "openai/o4-mini"],
    ["deepseek-r1:8b", "ollama/deepseek-r1:8b"],
    ["deepseek/deepseek-chat", "deepseek/deepseek-chat"],
  ])("interprets %s as %s, matching server routing", (configured, expected) => {
    const ai = defaultUserConfig().ai;
    expect(
      getChatModelId({
        ...ai,
        models: { ...ai.models, chat_model: configured },
      }).id,
    ).toBe(expected);
  });

  it("displays the legacy OpenAI model when no chat model is set", () => {
    const { current } = getChatModelConfig({
      ...defaultUserConfig().ai,
      open_ai: { model: "gpt-4-legacy" },
    });
    expect(current.id).toBe("openai/gpt-4-legacy");
  });

  it("offers custom models configured for edit and autocomplete in chat", () => {
    const ai = defaultUserConfig().ai;
    const { registry } = getChatModelConfig(
      { ...ai, models: { ...ai.models, edit_model: "ollama/team-coder" } },
      "ollama/team-complete",
    );
    expect(
      registry
        .getModelsByProvider("ollama")
        .filter((model) => model.custom)
        .map((model) => model.model),
    ).toEqual(["team-complete", "team-coder"]);
  });

  it("preserves the active model when excluded from the allowlist", () => {
    const { registry, reasoningOptions, displayName } = resolveModel(
      "openai/gpt-6.1-sol",
      ["openai/gpt-6-luna"],
    );
    expect(
      registry
        .getListModelsByProvider()
        .flatMap(([, models]) => models.map((model) => model.name)),
    ).toEqual(["GPT-6 Luna", "GPT-6.1 Sol"]);
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
  ])("uses catalog efforts regardless of provider for %s", (model) => {
    const { reasoningOptions } = resolveModel(model);
    expect(
      getEffectiveChatOptions(
        { webSearch: false, reasoningEffort: "max" },
        reasoningOptions,
      ),
    ).toEqual({ webSearch: false, reasoningEffort: "max" });
  });
});
