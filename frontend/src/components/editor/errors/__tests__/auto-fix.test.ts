/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { buildFixInChatPrompt } from "../auto-fix";

describe("buildFixInChatPrompt", () => {
  it("references the per-cell error context URI", () => {
    expect(buildFixInChatPrompt(cellId("cell-1"))).toBe(
      "@error://cell-1\n\nPlease fix this error.",
    );
  });

  it("falls back to inline error text when no cell id", () => {
    expect(buildFixInChatPrompt(undefined, "ValueError: boom")).toBe(
      "My code gives the following error. Please fix it:\n\nValueError: boom",
    );
  });

  it("uses a generic prompt when no cell id and no error text", () => {
    expect(buildFixInChatPrompt(undefined)).toBe("Please fix this error.");
  });
});
