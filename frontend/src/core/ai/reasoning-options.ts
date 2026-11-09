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

export function getReasoningEffortOptions(
  options: ReasoningOption[] = [],
): ReasoningEffortChoice[] {
  const efforts = options.flatMap((option) =>
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

export function getChatReasoningEffortOptions(
  model: AiModel | undefined,
  baseUrl?: string,
) {
  if (!model || model.provider === "azure") {
    return [];
  }
  if (model.provider === "openai" && baseUrl) {
    try {
      if (new URL(baseUrl).hostname !== "api.openai.com") {
        return [];
      }
    } catch {
      return [];
    }
  }
  return getReasoningEffortOptions(model.reasoning_options);
}
