/* Copyright 2024 Marimo. All rights reserved. */

import type { z } from "zod";
import type { CopilotMode } from "./registry";

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
