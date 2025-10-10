/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type { CopilotMode } from "./registry";

/**
 * Status value for tool responses, mirroring status value in marimo/_ai/_tools/types.py
 */
export type StatusValue = "success" | "error" | "warning";

/**
 * Base interface for tool output responses.
 * Mirrors the SuccessResult dataclass from marimo/_ai/_tools/types.py
 *
 * Tool outputs should extend this interface to include standardized
 * metadata like next_steps, messages, and status information.
 */
export interface ToolOutputBase {
  status?: StatusValue;
  auth_required?: boolean;
  next_steps?: string[];
  action_url?: string;
  message?: string;
  meta?: Record<string, unknown>;
}

/**
 * Base Zod schema for tool outputs.
 *
 * Tool output schemas should extend this using .extend() to add their specific fields.
 */
export const toolOutputBaseSchema = z.object({
  status: z.enum(["success", "error", "warning"]).optional(),
  auth_required: z.boolean().optional(),
  next_steps: z.array(z.string()).optional(),
  action_url: z.string().optional(),
  message: z.string().optional(),
  meta: z.record(z.string(), z.unknown()).optional(),
});

/**
 * Contract for a frontend tool.
 *
 * Implementations can be plain objects or classes. The registry consumes this
 * interface without caring about the underlying implementation.
 */
export interface AiTool<TIn, TOut> {
  name: string;
  description: string;
  schema: z.ZodType<TIn>;
  outputSchema: z.ZodType<TOut>;
  mode: CopilotMode[];
  handler: (args: TIn) => TOut | Promise<TOut>;
}
