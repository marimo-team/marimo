/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import type { IPluginProps } from "../../types";
import { TabsPlugin } from "../TabsPlugin";

describe("TabsPlugin", () => {
  beforeAll(() => {
    store.set(initialModeAtom, "edit");
  });

  const renderPlugin = (
    data: z.input<TabsPlugin["validator"]>,
    initialValue = "0",
  ) => {
    const plugin = new TabsPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();
    const children = [
      <span key="0">Content 0</span>,
      <span key="1">Content 1</span>,
      <span key="2">Content 2</span>,
    ];
    const makeProps = (
      value: string,
    ): IPluginProps<string, z.infer<TabsPlugin["validator"]>> => ({
      data: plugin.validator.parse(data),
      value,
      setValue,
      host,
      functions: {},
      children,
    });
    const result = render(plugin.render(makeProps(initialValue)));
    return {
      ...result,
      setValue,
      rerenderWithValue: (newValue: string) =>
        result.rerender(plugin.render(makeProps(newValue))),
    };
  };

  it("renders all tab triggers", () => {
    renderPlugin({
      tabs: ["First", "Second", "Third"],
      label: null,
    });
    expect(screen.getByRole("tab", { name: "First" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Second" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Third" })).toBeInTheDocument();
  });

  it("supports vertical orientation", () => {
    renderPlugin({
      tabs: ["First", "Second"],
      label: null,
      orientation: "vertical",
    });
    const tablist = screen.getByRole("tablist");
    expect(tablist).toHaveAttribute("data-orientation", "vertical");
    expect(tablist.className).toMatch(/flex-col/);
    // Horizontal scroll classes should not be applied in vertical mode.
    expect(tablist.className).not.toMatch(/overflow-x-auto/);
  });

  it("falls back to horizontal when orientation is omitted (back-compat)", () => {
    // Older Python kernels won't send `orientation` — make sure the validator
    // defaults it so the frontend keeps working.
    const plugin = new TabsPlugin();
    const parsed = plugin.validator.parse({
      tabs: ["First"],
      label: null,
    });
    expect(parsed.orientation).toBe("horizontal");
  });

  it("selects the tab matching the initial value", () => {
    renderPlugin({ tabs: ["First", "Second", "Third"], label: null }, "1");
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveAttribute("data-state", "inactive");
    expect(tabs[1]).toHaveAttribute("data-state", "active");
    expect(tabs[2]).toHaveAttribute("data-state", "inactive");
  });

  it("defaults to the first tab when value is empty", () => {
    renderPlugin({ tabs: ["First", "Second"], label: null }, "");
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveAttribute("data-state", "active");
    expect(tabs[1]).toHaveAttribute("data-state", "inactive");
  });

  it("calls setValue with the clicked tab's index", () => {
    const { setValue } = renderPlugin({
      tabs: ["First", "Second", "Third"],
      label: null,
    });
    // Radix Tabs' trigger reacts to mousedown (left button), not click —
    // see https://github.com/radix-ui/primitives/blob/main/packages/react/tabs/src/Tabs.tsx
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Third" }), {
      button: 0,
    });
    expect(setValue).toHaveBeenCalledWith("2");
  });

  it("syncs selection when value is updated externally", () => {
    const { rerenderWithValue } = renderPlugin(
      { tabs: ["First", "Second", "Third"], label: null },
      "0",
    );
    expect(screen.getAllByRole("tab")[0]).toHaveAttribute(
      "data-state",
      "active",
    );

    rerenderWithValue("2");
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveAttribute("data-state", "inactive");
    expect(tabs[2]).toHaveAttribute("data-state", "active");
  });

  it("renders HTML in tab labels via renderHTML", () => {
    renderPlugin({
      tabs: ["<strong>Bold</strong>", "Plain"],
      label: null,
    });
    const boldTab = screen.getByRole("tab", { name: "Bold" });
    // The label markup is preserved (not escaped as text), so the trigger
    // contains a real <strong> element.
    expect(boldTab.querySelector("strong")).not.toBeNull();
  });

  it("renders no tabpanels when tabs and children are empty", () => {
    // When the Python side passes `tabs={}`, slotted HTML is empty and the
    // resulting React children are null/undefined. We should render zero
    // `TabsContent`s — not a stray one paired to a non-existent trigger.
    const plugin = new TabsPlugin();
    const host = document.createElement("div");
    const props: IPluginProps<string, z.infer<TabsPlugin["validator"]>> = {
      data: plugin.validator.parse({ tabs: [], label: null }),
      value: "",
      setValue: vi.fn(),
      host,
      functions: {},
      children: null,
    };
    render(plugin.render(props));
    expect(screen.queryAllByRole("tab")).toHaveLength(0);
    expect(screen.queryAllByRole("tabpanel")).toHaveLength(0);
  });
});
