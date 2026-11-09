/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getKnownModelMaps } from "@/core/ai/model-registry";
import { chatOptionsAtom } from "@/core/ai/state";
import { userConfigAtom } from "@/core/config/config";
import { ChatModelPicker } from "../chat-model-picker";

const { saveModelChange, handleClick } = vi.hoisted(() => ({
  saveModelChange: vi.fn(),
  handleClick: vi.fn(),
}));
vi.mock("@/core/ai/config", () => ({
  useAIConfigActions: () => ({ saveModelChange }),
}));
vi.mock("@/components/app-config/state", () => ({
  useOpenSettingsToTab: () => ({ handleClick }),
}));

function renderPicker(reasoning: boolean) {
  const knownModel = [...getKnownModelMaps().modelMap.values()].find(
    (model) =>
      model.provider === "openai" &&
      model.roles.includes("chat") &&
      model.capabilities.includes("thinking"),
  );
  if (!knownModel) {
    throw new Error("Expected a known OpenAI reasoning model");
  }
  const model = reasoning
    ? knownModel
    : { ...knownModel, model: "custom-model", name: "custom-model" };
  const modelId = `${model.provider}/${model.model}`;
  const store = createStore();
  store.set(userConfigAtom, {
    ...store.get(userConfigAtom),
    ai: {
      models: { chat_model: modelId, custom_models: [], displayed_models: [] },
    },
  });
  render(
    <Provider store={store}>
      <ChatModelPicker />
    </Provider>,
  );
  fireEvent.click(screen.getByRole("button", { name: `Model: ${model.name}` }));
  return { store, model, modelId };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

describe("ChatModelPicker", () => {
  it("searches and selects a model while keeping reasoning accessible", () => {
    const { model, modelId } = renderPicker(true);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: model.model },
    });
    fireEvent.click(
      screen.getByRole("option", { name: `${model.name} (OpenAI)` }),
    );
    expect(saveModelChange).toHaveBeenCalledExactlyOnceWith(modelId, "chat");
    expect(
      screen.getByRole("radiogroup", { name: "Reasoning" }),
    ).toBeInTheDocument();
  });

  it("clears reasoning when selecting a different model", () => {
    const { store, modelId } = renderPicker(true);
    const alternate = [...getKnownModelMaps().modelMap.entries()].find(
      ([id, model]) =>
        id !== modelId &&
        model.provider === "openai" &&
        model.roles.includes("chat"),
    );
    if (!alternate) {
      throw new Error("Expected another chat model");
    }
    fireEvent.click(screen.getByRole("radio", { name: "High" }));
    fireEvent.click(
      screen.getByRole("option", { name: `${alternate[1].name} (OpenAI)` }),
    );
    expect(saveModelChange).toHaveBeenCalledExactlyOnceWith(
      alternate[0],
      "chat",
    );
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: false,
      reasoningEffort: null,
    });
  });

  it("updates reasoning without losing other chat settings", () => {
    const { store, model } = renderPicker(true);
    store.set(chatOptionsAtom, { webSearch: true });
    fireEvent.click(screen.getByRole("radio", { name: "High" }));
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: true,
      reasoningEffort: "high",
    });
    expect(
      screen.getByRole("button", {
        name: `Model: ${model.name}, reasoning: High, web search enabled`,
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Default" }));
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: true,
      reasoningEffort: null,
    });
  });

  it("shows the selected model's full effort list", () => {
    const { store } = renderPicker(true);
    expect(
      screen
        .getAllByRole("radio")
        .map((radio) => radio.closest("label")?.textContent),
    ).toEqual(["Default", "Low", "Medium", "High", "Extra high", "Max"]);
    fireEvent.click(screen.getByRole("radio", { name: "Extra high" }));
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: false,
      reasoningEffort: "xhigh",
    });
    fireEvent.click(screen.getByRole("radio", { name: "Max" }));
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: false,
      reasoningEffort: "max",
    });
  });

  it("hides effort choices for models without reasoning support", () => {
    renderPicker(false);
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
    expect(
      screen.getByText("This model uses its default reasoning settings."),
    ).toBeInTheDocument();
  });

  it("filters models by provider and clears the previous search", () => {
    renderPicker(true);
    const providers = screen.getByRole("navigation", {
      name: "Model providers",
    });
    expect(
      within(providers).getByRole("button", { name: "OpenAI" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.queryByRole("option", { name: /\(Anthropic\)$/ }),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "no-such-model" },
    });
    expect(screen.getByText("No models found.")).toBeInTheDocument();
    fireEvent.click(
      within(providers).getByRole("button", { name: "Anthropic" }),
    );
    expect(screen.getByRole("combobox")).toHaveValue("");
    expect(
      within(providers).getByRole("button", { name: "Anthropic" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen
        .getAllByRole("option")
        .every((option) =>
          option.getAttribute("aria-label")?.endsWith("(Anthropic)"),
        ),
    ).toBe(true);
  });

  it("toggles web search inside the picker without changing reasoning", () => {
    const { store } = renderPicker(true);
    fireEvent.click(screen.getByRole("radio", { name: "High" }));
    fireEvent.click(screen.getByRole("switch", { name: "Web search" }));
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: true,
      reasoningEffort: "high",
    });
    expect(screen.getByRole("switch", { name: "Web search" })).toBeChecked();
    expect(
      screen.getByRole("button", { name: /Model: .*web search enabled/ }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("switch", { name: "Web search" }));
    expect(store.get(chatOptionsAtom)).toEqual({
      webSearch: false,
      reasoningEffort: "high",
    });
  });

  it("opens model settings", () => {
    renderPicker(true);
    fireEvent.click(screen.getByRole("button", { name: "Manage models" }));
    expect(handleClick).toHaveBeenCalledExactlyOnceWith("ai", "ai-models");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
