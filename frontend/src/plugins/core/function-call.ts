/* Copyright 2026 Marimo. All rights reserved. */

import { type ZodSchema, z } from "zod";
import type { FunctionRequest } from "@/core/functions/host-function";
import { FunctionNotFoundError } from "@/utils/errors";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";

// Retry only missing registrations. A function that ran can have side effects.
const FUNCTION_NOT_FOUND_MAX_RETRIES = 3;
const FUNCTION_NOT_FOUND_BASE_DELAY_MS = 150;

/** Validate the existing function contract independently of its transport. */
export async function callPluginFunction<T>({
  name,
  args,
  input,
  output,
  getNamespace,
  request,
}: {
  name: string;
  args: unknown;
  input: ZodSchema<Record<string, unknown>>;
  output: ZodSchema<T>;
  getNamespace: () => string | null;
  request: FunctionRequest;
}): Promise<T> {
  const parsedArgs = prettyParse(input, args);
  for (let attempt = 0; ; attempt++) {
    // A re-render can correct an object id before registration catches up.
    const namespace = getNamespace();
    invariant(namespace, "Object ID should exist");
    const response = await request({
      args: parsedArgs,
      functionName: name,
      namespace,
    });
    if (response.status.code === "ok") {
      return prettyParse(output, response.return_value);
    }
    const recoverable = response.found === false;
    if (recoverable && attempt < FUNCTION_NOT_FOUND_MAX_RETRIES) {
      const delay = FUNCTION_NOT_FOUND_BASE_DELAY_MS * 2 ** attempt;
      await new Promise((resolve) => setTimeout(resolve, delay));
      continue;
    }
    Logger.error(response.status);
    if (recoverable) {
      throw new FunctionNotFoundError();
    }
    throw new Error(response.status.message || "Unknown error");
  }
}

function prettyParse<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    Logger.log("Failed to parse data", data, result.error);
    throw new Error(z.prettifyError(result.error));
  }
  return result.data;
}
