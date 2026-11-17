/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { OutlineItem } from "@/core/cells/outline";
import { MiniMap, OutlineList } from "../floating-outline";
import { scrollToOutlineItem } from "../useActiveOutline";

vi.mock("../useActiveOutline", () => ({ scrollToOutlineItem: vi.fn() }));

const items: OutlineItem[] = [
  { name: "First", level: 1, by: { id: "first" } },
  { name: "Second", html: "<em>Second</em>", level: 2, by: { id: "second" } },
];

describe("outline keyboard navigation", () => {
  it.each([
    { Component: MiniMap, role: "button" },
    { Component: OutlineList, role: "link" },
  ])(
    "keeps the focused $role when other headings change",
    ({ Component, role }) => {
      const duplicate: OutlineItem = {
        name: "Repeated second",
        level: 2,
        by: { id: "second" },
      };
      const initial = [...items, duplicate];
      const props = {
        activeHeaderId: undefined,
        activeOccurrences: undefined,
      };
      const { rerender } = render(<Component {...props} items={initial} />);
      const focused = screen.getByRole(role, { name: "Repeated second" });
      focused.focus();

      for (const by of [{ id: "inserted" }, { path: "second" }]) {
        const inserted: OutlineItem = { name: "Inserted", level: 1, by };
        rerender(<Component {...props} items={[inserted, ...initial]} />);
        expect(screen.getByRole(role, { name: "Repeated second" })).toBe(
          focused,
        );
        expect(focused).toHaveFocus();
      }

      rerender(
        <Component {...props} items={[items[1], duplicate, items[0]]} />,
      );
      expect(screen.getByRole(role, { name: "Repeated second" })).toBe(focused);
      expect(focused).toHaveFocus();
      fireEvent.click(focused);
      expect(scrollToOutlineItem).toHaveBeenLastCalledWith(duplicate, 1);
    },
  );

  it("activates plain and rich headings with Enter", () => {
    render(
      <OutlineList
        items={items}
        activeHeaderId={undefined}
        activeOccurrences={undefined}
      />,
    );
    items.forEach((item) => {
      const link = screen.getByRole("link", { name: item.name });
      expect(link).toHaveAttribute("tabindex", "0");
      fireEvent.keyDown(link, { key: "Enter" });
      expect(scrollToOutlineItem).toHaveBeenLastCalledWith(item, 0);
    });
  });

  it("names each minimap button", () => {
    render(
      <MiniMap
        items={items}
        activeHeaderId={undefined}
        activeOccurrences={undefined}
      />,
    );
    const button = screen.getByRole("button", { name: "Second" });
    fireEvent.click(button);
    expect(scrollToOutlineItem).toHaveBeenLastCalledWith(items[1], 0);
  });
});
