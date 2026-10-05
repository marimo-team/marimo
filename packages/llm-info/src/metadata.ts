/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";

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
  capabilities: z.array(z.enum(["thinking", "tool_calling"])).default([]),
  cost: z
    .object({ input: z.number().optional(), output: z.number().optional() })
    .optional(),
  limits: ModelLimitsSchema.optional(),
});

export type ExistingMetadata = z.infer<typeof ExistingMetadataSchema>;
