/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { beforeEach, describe, expect, it } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  chatModelConfigAtom,
  effectiveChatOptionsAtom,
} from "../chat-model-config";
import { chatOptionsAtom } from "../state";

function createChatStore(
  model = "openai/gpt-6-luna",
  displayed: string[] = [],
  baseUrl?: string,
) {
  const store = createStore();
  store.set(userConfigAtom, {
    ...store.get(userConfigAtom),
    ai: {
      open_ai: { base_url: baseUrl },
      models: {
        chat_model: model,
        custom_models: [],
        displayed_models: displayed,
      },
    },
  });
  return store;
}

beforeEach(() => localStorage.clear());

describe("chat model configuration", () => {
  it("preserves the active model when excluded from the allowlist", () => {
    const store = createChatStore("openai/gpt-6.1-sol", ["openai/gpt-6-luna"]);
    const { registry, reasoningOptions, displayName } =
      store.get(chatModelConfigAtom);
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
    const store = createChatStore();
    store.set(chatOptionsAtom, { webSearch: true, reasoningEffort: "none" });
    expect(store.get(effectiveChatOptionsAtom)).toEqual({
      webSearch: true,
      reasoningEffort: "none",
    });
    store.set(userConfigAtom, (previous) => ({
      ...previous,
      ai: {
        ...previous.ai,
        models: {
          custom_models: [],
          displayed_models: [],
          chat_model: "openai/gpt-6.1-sol",
        },
      },
    }));
    expect(store.get(effectiveChatOptionsAtom)).toEqual({
      webSearch: true,
      reasoningEffort: null,
    });
  });

  it("does not send efforts for unknown models", () => {
    const store = createChatStore("openai/custom-model");
    store.set(chatOptionsAtom, { webSearch: false, reasoningEffort: "high" });
    expect(store.get(effectiveChatOptionsAtom)).toEqual({
      webSearch: false,
      reasoningEffort: null,
    });
  });

  it.each([
    [undefined, true],
    ["https://api.openai.com/v1", true],
    ["https://API.OPENAI.COM/v1", true],
    ["https://api.openai.com.attacker.example/v1", false],
    ["https://custom.example/api.openai.com", false],
    ["invalid-url", false],
  ] as const)("checks the hostname of %s", (baseUrl, supported) => {
    const store = createChatStore("openai/gpt-6.1-sol", [], baseUrl);
    store.set(chatOptionsAtom, { webSearch: true, reasoningEffort: "high" });
    expect(store.get(effectiveChatOptionsAtom)).toEqual({
      webSearch: true,
      reasoningEffort: supported ? "high" : null,
    });
  });
});
