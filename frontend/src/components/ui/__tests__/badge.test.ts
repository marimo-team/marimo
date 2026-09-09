/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { badgeVariants } from "../badge";

describe("badgeVariants", () => {
  it.each([
    {
      variant: "default" as const,
      expected: [
        "forced-colors:bg-[Highlight]",
        "forced-colors:border-[Highlight]",
        "forced-colors:text-[HighlightText]",
        "forced-colors:hover:bg-[Highlight]",
        "forced-colors:hover:text-[HighlightText]",
      ],
    },
    {
      variant: "defaultOutline" as const,
      expected: [
        "forced-colors:bg-[Canvas]",
        "forced-colors:border-[Highlight]",
        "forced-colors:text-[CanvasText]",
      ],
    },
    {
      variant: "secondary" as const,
      expected: [
        "forced-colors:bg-[ButtonFace]",
        "forced-colors:border-[ButtonText]",
        "forced-colors:text-[ButtonText]",
        "forced-colors:hover:bg-[Highlight]",
        "forced-colors:hover:text-[HighlightText]",
      ],
    },
  ])("uses system colors for $variant", ({ variant, expected }) => {
    const classes = badgeVariants({ variant });

    expect(classes).toEqual(expect.stringContaining(expected.join(" ")));
    expect(classes).toContain("forced-color-adjust-none");
  });

  it.each(["destructive", "success", "outline"] as const)(
    "keeps the %s variant visible without semantic colors",
    (variant) => {
      const classes = badgeVariants({ variant });

      expect(classes).toEqual(
        expect.stringContaining(
          [
            "forced-colors:bg-[Canvas]",
            "forced-colors:border-[ButtonText]",
            "forced-colors:text-[CanvasText]",
          ].join(" "),
        ),
      );
      if (variant !== "outline") {
        expect(classes).toContain("forced-colors:hover:bg-[Highlight]");
        expect(classes).toContain("forced-colors:hover:text-[HighlightText]");
      }
    },
  );
});
