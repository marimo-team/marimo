/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, test } from "vitest";
import { MermaidPlugin } from "../mermaid/MermaidPlugin";

describe("MermaidPlugin validator", () => {
  test("accepts optional theme and theme_variables", () => {
    const plugin = new MermaidPlugin();
    const result = plugin.validator.safeParse({
      diagram: "graph TD\nA --> B",
      theme: "base",
      theme_variables: {
        primaryColor: "#E8EEF5",
        lineColor: "#475569",
      },
    });

    expect(result.success).toBe(true);
    if (!result.success) {
      return;
    }

    expect(result.data).toEqual({
      diagram: "graph TD\nA --> B",
      theme: "base",
      theme_variables: {
        primaryColor: "#E8EEF5",
        lineColor: "#475569",
      },
    });
  });

  test("accepts any string as theme", () => {
    const plugin = new MermaidPlugin();
    const result = plugin.validator.safeParse({
      diagram: "graph TD\nA --> B",
      theme: "invalid",
    });

    expect(result.success).toBe(true);
    if (!result.success) {
      return;
    }

    expect(result.data).toEqual({
      diagram: "graph TD\nA --> B",
      theme: "invalid",
    });
  });
});
