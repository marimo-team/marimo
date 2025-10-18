/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type { CopilotMode } from "./registry";

/**
 * Status value for tool responses, mirroring status value in marimo/_ai/_tools/types.py
 */
export type StatusValue = "success" | "error" | "warning";

/**
 * Structured error for tool execution failures.
 * Mirrors the ToolExecutionError dataclass from marimo/_ai/_tools/utils/exceptions.py
 *
 * @example
 * throw new ToolExecutionError(
 *   "Failed to fetch data",
 *   "FETCH_ERROR",
 *   true,
 *   "Check your network connection"
 * );
 */
export class ToolExecutionError extends Error {
  readonly code: string;
  readonly isRetryable: boolean;
  readonly suggestedFix?: string;
  readonly meta?: Record<string, unknown>;

  constructor(
    message: string,
    code = "TOOL_ERROR",
    isRetryable = false,
    suggestedFix?: string,
    meta?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ToolExecutionError";
    this.code = code;
    this.isRetryable = isRetryable;
    this.suggestedFix = suggestedFix;
    this.meta = meta;
  }

  toStructuredString(): string {
    const stringError = JSON.stringify({
      message: this.message,
      code: this.code,
      is_retryable: this.isRetryable,
      suggested_fix: this.suggestedFix,
      meta: this.meta ?? {},
    });
    return `Error invoking tool ${this.name}: ${stringError}`;
  }
}

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

export interface ToolDescription {
  baseDescription: string;
  whenToUse?: string[];
  avoidIf?: string[];
  prerequisites?: string[];
  sideEffects?: string[];
  additionalInfo?: string;
}

export interface AiTool<TIn, TOut> {
  name: string;
  description: ToolDescription;
  schema: z.ZodType<TIn>;
  outputSchema: z.ZodType<TOut>;
  mode: CopilotMode[];
  handler: (args: TIn) => TOut | Promise<TOut>;
}
