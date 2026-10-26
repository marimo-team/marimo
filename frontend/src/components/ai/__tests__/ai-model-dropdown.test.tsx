/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getKnownModelMaps } from "@/core/ai/model-registry";
import { AIModelDropdown } from "../ai-model-dropdown";
import * as aiUtils from "../ai-utils";

vi.mock("@/core/ai/config", () => ({
  useAIConfigActions: () => ({ saveModelChange: vi.fn() }),
}));
vi.mock("@/components/app-config/state", () => ({
  useOpenSettingsToTab: () => ({ handleClick: vi.fn() }),
}));

it.each(["Enter", " "])(
  "selects a model with %j while ArrowRight retains information access",
  async (key) => {
    const knownModel = [...getKnownModelMaps().modelMap.values()].find(
      (model) => model.provider === "openai",
    );
    if (!knownModel) {
      throw new Error("Expected a known OpenAI model");
    }
    const model = { ...knownModel, capabilities: [] };
    vi.spyOn(aiUtils, "listModelsForAiSettings").mockReturnValue([
      [model.provider, [model]],
    ]);
    const onSelect = vi.fn();
    render(
      <Provider store={createStore()}>
        <TooltipProvider>
          <AIModelDropdown
            forRole="chat"
            placeholder="Choose model"
            onSelect={onSelect}
          />
        </TooltipProvider>
      </Provider>,
    );
    fireEvent.keyDown(screen.getByRole("button", { name: "Choose model" }), {
      key: "ArrowDown",
    });
    fireEvent.keyDown(
      await screen.findByRole("menuitem", { name: /OpenAI$/ }),
      { key: "ArrowRight" },
    );
    const option = await screen.findByRole("menuitem", {
      name: (name) => name.endsWith(model.name),
    });
    fireEvent.keyDown(option, { key: "ArrowRight" });
    expect(
      await screen.findByRole("heading", { name: model.name }),
    ).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.keyDown(option, { key });
    expect(onSelect).toHaveBeenCalledExactlyOnceWith(
      `${model.provider}/${model.model}`,
    );
  },
);
