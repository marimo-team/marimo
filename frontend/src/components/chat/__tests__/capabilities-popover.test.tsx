/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it } from "vitest";
import { chatOptionsAtom } from "@/core/ai/state";
import { CapabilitiesPopover } from "../capabilities-popover";

describe("CapabilitiesPopover", () => {
  it("updates ephemeral chat options", () => {
    const store = createStore();

    render(
      <Provider store={store}>
        <CapabilitiesPopover />
      </Provider>,
    );

    const trigger = screen.getByRole("button", { name: "Capabilities" });
    expect(trigger).not.toHaveAttribute("data-active");

    fireEvent.click(trigger);
    const webSearch = screen.getByRole("switch", { name: "Web search" });
    expect(webSearch).not.toBeChecked();

    fireEvent.click(webSearch);

    expect(webSearch).toBeChecked();
    expect(trigger).toHaveAttribute("data-active", "true");
    expect(trigger).toHaveClass("bg-primary/15", "text-primary", "ring-1");
    expect(trigger).toHaveAttribute(
      "title",
      "Capabilities (web search enabled)",
    );
    expect(store.get(chatOptionsAtom)).toEqual({ webSearch: true });
    expect(createStore().get(chatOptionsAtom)).toEqual({ webSearch: false });
  });
});
