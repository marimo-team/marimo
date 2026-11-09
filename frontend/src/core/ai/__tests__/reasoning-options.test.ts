/* Copyright 2026 Marimo. All rights reserved. */

import type { ReasoningOption } from "@marimo-team/llm-info";
import { describe, expect, it } from "vitest";
import { getChatReasoningOptions } from "../reasoning-options";
import type { AiModelReasoningResponse } from "@/core/network/types";

const supported: AiModelReasoningResponse["efforts"] = [
  "none",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
];

describe("getChatReasoningOptions", () => {
  it("preserves the model's effort choices and ordering", () => {
    expect(
      getChatReasoningOptions(
        {
          reasoning_options: [
            {
              type: "effort",
              values: ["none", "minimal", "low", "high", "xhigh", "max"],
            },
          ],
        },
        supported,
      ),
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
      getChatReasoningOptions(
        {
          reasoning_options: [
            { type: "effort", values: [null, "default", "medium", "medium"] },
          ],
        },
        supported,
      ),
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
    expect(
      getChatReasoningOptions({ reasoning_options: options }, supported),
    ).toEqual([]);
  });
  it("only offers efforts supported by both the catalog and runtime", () => {
    expect(
      getChatReasoningOptions(
        {
          reasoning_options: [
            { type: "effort", values: ["low", "high", "max"] },
          ],
        },
        ["low", "high"],
      ),
    ).toEqual([
      { value: "default", label: "Default" },
      { value: "low", label: "Low" },
      { value: "high", label: "High" },
    ]);
    expect(
      getChatReasoningOptions(
        { reasoning_options: [{ type: "effort", values: ["max"] }] },
        [],
      ),
    ).toEqual([]);
  });
});
