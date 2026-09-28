/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  menuControlVariants,
  menuItemVariants,
  menuSubTriggerVariants,
} from "../menu-items";

describe("menu item variants", () => {
  it.each([
    menuSubTriggerVariants(),
    menuControlVariants(),
    menuItemVariants(),
  ])("styles Radix highlighted state", (classes) => {
    expect(classes).toContain("data-[highlighted]:bg-accent");
    expect(classes).toContain(
      "forced-colors:data-[highlighted]:bg-[Highlight]",
    );
    expect(classes).toContain(
      "forced-colors:data-[highlighted]:text-[HighlightText]",
    );
  });

  it("keeps the command item selected state", () => {
    const classes = menuItemVariants();

    expect(classes).toContain("aria-selected:bg-accent");
    expect(classes).toContain("forced-colors:aria-selected:bg-[Highlight]");
  });
});
