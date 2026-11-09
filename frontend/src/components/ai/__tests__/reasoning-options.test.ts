/* Copyright 2026 Marimo. All rights reserved. */

import type { ReasoningOption } from "@marimo-team/llm-info";
import { describe, expect, it } from "vitest";
import { getReasoningEffortOptions } from "@/core/ai/reasoning-options";

describe("getReasoningEffortOptions", () => {
  it("preserves the model's effort choices and ordering", () => {
    expect(
      getReasoningEffortOptions([
        {
          type: "effort",
          values: ["none", "minimal", "low", "high", "xhigh", "max"],
        },
      ]),
    ).toEqual([
      { value: "default", label: "Default" },
      { value: "none", label: "None" },
      { value: "minimal", label: "Minimal" },
      { value: "low", label: "Low" },
      { value: "high", label: "High" },
      { value: "xhigh", label: "Extra high" },
      { value: "max", label: "Max" },
    ]);
  });

  it("offers one default choice for provider defaults and null", () => {
    expect(
      getReasoningEffortOptions([
        { type: "effort", values: [null, "default", "medium", "medium"] },
      ]),
    ).toEqual([
      { value: "default", label: "Default" },
      { value: "medium", label: "Medium" },
    ]);
  });

  it.each<{ options: ReasoningOption[] | undefined }>([
    { options: undefined },
    { options: [] },
    { options: [{ type: "toggle" }] },
    { options: [{ type: "budget_tokens", min: -1, max: 32768 }] },
    { options: [{ type: "effort", values: [] }] },
  ])("does not invent effort choices for $options", ({ options }) => {
    expect(getReasoningEffortOptions(options)).toEqual([]);
  });
});
