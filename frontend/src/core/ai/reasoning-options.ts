/* Copyright 2026 Marimo. All rights reserved. */

import type { AiModel } from "./model-registry";
import type { AiModelReasoningResponse } from "@/core/network/types";
import type { ReasoningOption } from "@marimo-team/llm-info";

type ReasoningEffort = NonNullable<
  Extract<ReasoningOption, { type: "effort" }>["values"][number]
>;

const EFFORT_LABELS = {
  none: "None",
  minimal: "Minimal",
  low: "Low",
  medium: "Medium",
  high: "High",
  xhigh: "Extra high",
  max: "Max",
  default: "Default",
} satisfies Record<ReasoningEffort, string>;

export interface ReasoningEffortChoice {
  value: ReasoningEffort;
  label: string;
}

export function getChatReasoningOptions(
  model: Pick<AiModel, "reasoning_options"> | undefined,
  supportedEfforts: AiModelReasoningResponse["efforts"],
): ReasoningEffortChoice[] {
  if (!model) {
    return [];
  }
  const values = new Set<ReasoningEffort>();
  for (const option of model.reasoning_options ?? []) {
    if (option.type !== "effort") {
      continue;
    }
    for (const value of option.values) {
      if (
        value !== null &&
        value !== "default" &&
        supportedEfforts.some((effort) => effort === value)
      ) {
        values.add(value);
      }
    }
  }
  if (values.size === 0) {
    return [];
  }
  return [
    { value: "default", label: EFFORT_LABELS.default },
    ...[...values].map((value) => ({ value, label: EFFORT_LABELS[value] })),
  ];
}
