/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { ZodType } from "zod";

export type PluginFunction<REQ = any, RES = any> = (args: REQ) => Promise<RES>;

/**
 * Functions that can be called from the plugin.
 */
export type PluginFunctions = Record<string, PluginFunction>;

// Utility types for extracting schemas from functions.
export type ExtractInputSchema<F extends PluginFunction> = F extends (
  args: infer REQ,
) => Promise<any>
  ? ZodType<REQ>
  : never;
export type ExtractOutputSchema<F extends PluginFunction> = F extends (
  args: any,
) => Promise<infer RES>
  ? ZodType<RES>
  : never;

/**
 * Schemas for the plugin functions.
 */
export type FunctionSchemas<F extends PluginFunctions> = {
  [K in keyof F]: {
    /**
     * Validate the function arguments.
     */
    input: ExtractInputSchema<F[K]>;
    /**
     * Validate the function output.
     */
    output: ExtractOutputSchema<F[K]>;
  };
};

/**
 * RPC builder for plugin functions.
 */
export const rpc = {
  input<I>(inputSchema: ZodType<I>) {
    return {
      output<O>(outputSchema: ZodType<O>) {
        return {
          input: inputSchema,
          output: outputSchema,
        };
      },
    };
  },
};
