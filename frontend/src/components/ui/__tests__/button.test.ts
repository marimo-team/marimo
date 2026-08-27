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
        "border-destructive",
        "hover:bg-destructive/90",
      ],
    },
    {
      variant: "success" as const,
      expected: [
        "bg-success",
        "text-success-foreground",
        "border-success",
        "hover:bg-success/90",
      ],
    },
    {
      variant: "warn" as const,
      expected: [
        "bg-action",
        "text-action-foreground",
        "border-action",
        "hover:bg-action-hover",
      ],
    },
  ])("uses semantic theme colors for $variant", ({ variant, expected }) => {
    const classes = buttonVariants({ variant });

    expect(classes).toEqual(expect.stringContaining(expected.join(" ")));
    expect(classes).not.toMatch(/--(?:red|grass|yellow)-/);
    expect(classes).not.toContain("dark:");
  });
});
