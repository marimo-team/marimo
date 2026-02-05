/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { ToolDescription } from "../base";
import { formatToolDescription } from "../utils";

describe("formatToolDescription", () => {
  it("formats a basic description only", () => {
    const description: ToolDescription = {
      baseDescription: "This is a simple tool",
    };

    expect(formatToolDescription(description)).toMatchInlineSnapshot(
      `"This is a simple tool"`,
    );
  });

  it("formats description with whenToUse", () => {
    const description: ToolDescription = {
      baseDescription: "Edit notebook cells",
      whenToUse: [
        "When user requests code changes",
        "When refactoring is needed",
      ],
    };

    expect(formatToolDescription(description)).toMatchInlineSnapshot(`
      "Edit notebook cells

      ## When to use:
      - When user requests code changes
      - When refactoring is needed"
    `);
  });

  it("formats description with all fields", () => {
    const description: ToolDescription = {
      baseDescription: "A comprehensive tool",
      whenToUse: ["Use case 1", "Use case 2"],
      avoidIf: ["Avoid case 1", "Avoid case 2"],
      prerequisites: ["Prerequisite 1", "Prerequisite 2"],
      sideEffects: ["Side effect 1", "Side effect 2"],
      additionalInfo: "Some extra context and notes.",
    };

    expect(formatToolDescription(description)).toMatchInlineSnapshot(`
      "A comprehensive tool

      ## When to use:
      - Use case 1
      - Use case 2

      ## Avoid if:
      - Avoid case 1
      - Avoid case 2

      ## Prerequisites:
      - Prerequisite 1
      - Prerequisite 2

      ## Side effects:
      - Side effect 1
      - Side effect 2

      ## Additional info:
      - Some extra context and notes."
    `);
  });

  it("formats description with only some fields", () => {
    const description: ToolDescription = {
      baseDescription: "A selective tool",
      avoidIf: ["Don't use in production"],
      sideEffects: ["Modifies state"],
    };

    expect(formatToolDescription(description)).toMatchInlineSnapshot(`
      "A selective tool

      ## Avoid if:
      - Don't use in production

      ## Side effects:
      - Modifies state"
    `);
  });
});
