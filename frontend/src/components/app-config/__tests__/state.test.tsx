/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ConfigButton } from "../app-config-button";
import { aiSettingsSubTabAtom, useOpenSettingsToTab } from "../state";
import { activeUserConfigCategoryAtom } from "../user-config-form";

vi.mock("../user-config-form", async () => {
  const { atom } = await import("jotai");
  return {
    activeUserConfigCategoryAtom: atom("editor"),
    UserConfigForm: () => <div>Settings form</div>,
  };
});
vi.mock("../app-config-form", () => ({
  AppConfigForm: () => null,
}));

function OpenAiSettings() {
  const { handleClick } = useOpenSettingsToTab();
  return (
    <button type="button" onClick={() => handleClick("ai")}>
      AI Settings
    </button>
  );
}

describe("useOpenSettingsToTab", () => {
  it("opens the settings dialog on the AI category from an external button", () => {
    const store = createStore();
    render(
      <Provider store={store}>
        <TooltipProvider>
          <OpenAiSettings />
          <ConfigButton />
        </TooltipProvider>
      </Provider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "AI Settings" }));

    expect(screen.getByRole("dialog", { name: "User settings" })).toBeVisible();
    expect(store.get(activeUserConfigCategoryAtom)).toBe("ai");
    expect(store.get(aiSettingsSubTabAtom)).toBe("ai-features");
  });
});
