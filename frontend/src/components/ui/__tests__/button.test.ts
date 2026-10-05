/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { buttonVariants } from "../button";

describe("buttonVariants", () => {
  it.each([
    {
      variant: "destructive" as const,
      expected: [
        "bg-destructive",
        "text-destructive-foreground",
        "border-destructive-border",
        "hover:bg-destructive-hover",
      ],
    },
    {
      variant: "success" as const,
      expected: [
        "bg-success",
        "text-success-foreground",
        "border-success-border",
        "hover:bg-success-hover",
      ],
    },
    {
      variant: "warn" as const,
      expected: [
        "bg-action",
        "text-action-foreground",
        "border-action-border",
        "hover:bg-action-hover",
      ],
    },
  ])("uses semantic theme colors for $variant", ({ variant, expected }) => {
    const classes = buttonVariants({ variant });

    expect(classes).toEqual(expect.stringContaining(expected.join(" ")));
    expect(classes).not.toMatch(/--(?:red|grass|yellow)-/);
    expect(classes).not.toContain("dark:");
  });

  it("uses system colors in forced-color mode", () => {
    const classes = buttonVariants({ variant: "default" });

    expect(classes).toEqual(
      expect.stringContaining(
        [
          "forced-color-adjust-none",
          "forced-colors:border-[ButtonText]",
          "forced-colors:bg-[ButtonFace]",
          "forced-colors:text-[ButtonText]",
          "forced-colors:hover:bg-[Highlight]",
          "forced-colors:hover:text-[HighlightText]",
          "forced-colors:disabled:border-[GrayText]",
          "forced-colors:disabled:text-[GrayText]",
        ].join(" "),
      ),
    );
  });
});
