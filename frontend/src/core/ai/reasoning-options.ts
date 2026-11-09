/* Copyright 2026 Marimo. All rights reserved. */

import type { AiModel } from "./model-registry";
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
): ReasoningEffortChoice[] {
  const efforts = (model?.reasoning_options ?? []).flatMap((option) =>
    option.type === "effort" ? option.values : [],
  );
  if (efforts.length === 0) {
    return [];
  }
  const values = new Set<ReasoningEffort>([
    "default",
    ...efforts.filter((effort) => effort !== null),
  ]);
  return [...values].map((value) => ({ value, label: EFFORT_LABELS[value] }));
}
