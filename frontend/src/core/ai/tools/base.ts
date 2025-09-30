/* Copyright 2024 Marimo. All rights reserved. */

import type { z } from "zod";
import type { AnyZodObject, CopilotMode } from "./registry";

/**
 * Contract for a frontend tool.
 *
 * Implementations can be plain objects or classes. The registry consumes this
 * interface without caring about the underlying implementation.
 */
export interface BaseTool<TIn extends AnyZodObject, TOut extends AnyZodObject> {
  name: string;
  description: string;
  schema: TIn;
  outputSchema: TOut;
  mode: CopilotMode[];
  handler: (args: z.infer<TIn>) => z.infer<TOut> | Promise<z.infer<TOut>>;
}
