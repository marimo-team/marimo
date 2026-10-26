/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { userConfigAtom } from "@/core/config/config";
import { defaultUserConfig } from "@/core/config/config-schema";
import { getDefaultHotkey } from "@/core/hotkeys/hotkeys";
import { KeyboardShortcuts, keyboardShortcutsAtom } from "../keyboard-shortcuts";

const saveUserConfig = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ saveUserConfig }),
}));

describe("shortcut recorder keyboard navigation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("allows Tab navigation and Reset without saving a shortcut", async () => {
    const store = createStore();
    const config = defaultUserConfig();
    store.set(userConfigAtom, {
      ...config,
      keymap: { ...config.keymap, overrides: { "cell.run": "Ctrl-9" } },
    });
    store.set(keyboardShortcutsAtom, true);
    render(
      <Provider store={store}>
        <TooltipProvider>
          <KeyboardShortcuts />
        </TooltipProvider>
      </Provider>,
    );
    const edit = screen.getByRole("button", {
      name: `Edit shortcut: ${getDefaultHotkey("cell.run").name}`,
    });
    act(() => edit.focus());
    fireEvent.click(edit, { detail: 0 });
    const recorder = screen.getByPlaceholderText(getDefaultHotkey("cell.run").name);
    expect(recorder).toHaveFocus();
    expect(fireEvent.keyDown(recorder, { key: "Tab" })).toBe(true);
    expect(fireEvent.keyDown(recorder, { key: "Tab", shiftKey: true })).toBe(true);
    expect(recorder).toBeInTheDocument();
    expect(saveUserConfig).not.toHaveBeenCalled();
    const reset = screen.getByRole("button", { name: /^Reset to default:/ });
    act(() => reset.focus());
    expect(reset).toHaveFocus();
    await act(async () => fireEvent.click(reset, { detail: 0 }));
    expect(saveUserConfig).toHaveBeenCalledExactlyOnceWith({
      config: { keymap: { ...config.keymap, overrides: {} } },
    });
  });
});
