/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";

export const CAPABILITIES = ["thinking", "tool_calling"] as const;

/** USD per million tokens; missing prices are unknown. */
export const CostSchema = z.object({
  input: z.number().optional(),
  output: z.number().optional(),
});

export const ReasoningEffortSchema = z.enum([
  "none",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
  "default",
]);

/** Mirrors models.dev; null is a provider option distinct from an omitted field. */
export const ReasoningOptionSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("toggle") }),
  z.object({
    type: z.literal("effort"),
    values: z.array(ReasoningEffortSchema.nullable()),
  }),
  z
    .object({
      type: z.literal("budget_tokens"),
      min: z.number().int().min(-1).optional(),
      max: z.number().int().nonnegative().optional(),
    })
    .refine(
      ({ min, max }) => min === undefined || max === undefined || min <= max,
      {
        message: "Minimum reasoning budget cannot exceed maximum",
        path: ["min"],
      },
    ),
]);

export const ModelLimitsSchema = z.object({
  context: z.number().int().nonnegative().optional(),
  output: z.number().int().nonnegative().optional(),
});

export type ReasoningOption = z.infer<typeof ReasoningOptionSchema>;
export type ModelLimits = z.infer<typeof ModelLimitsSchema>;

export const ExistingMetadataSchema = z.object({
  reasoning_options: z.array(ReasoningOptionSchema).optional(),
  capabilities: z.array(z.enum(CAPABILITIES)).default([]),
  cost: CostSchema.optional(),
  limits: ModelLimitsSchema.optional(),
});

export type ExistingMetadata = z.infer<typeof ExistingMetadataSchema>;

export type AiModelCost = z.infer<typeof CostSchema>;
