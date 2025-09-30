/* Copyright 2024 Marimo. All rights reserved. */

import { type ZodObject, z } from "zod";
import type { BaseTool } from "./base";
import { testFrontendTool } from "./sample-tool";
import { Memoize } from "typescript-memoize";
import type { components } from "@marimo-team/marimo-api"

export type AnyZodObject = ZodObject<z.ZodRawShape>;

// Generic type to avoid type errors
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type StoredTool = BaseTool<any, any>;

/** should be the same as marimo/_config/config.py > CopilotMode */
export type CopilotMode = "manual" | "ask";

type ToolDefinition = components["schemas"]["ToolDefinition"];

export interface FrontendToolDefinition extends ToolDefinition {
  source: "frontend";
}

export class FrontendToolRegistry {
  /** All registered tools */
  private tools = new Map<string, StoredTool>();

  constructor(
    // Accept any concrete tool generics; we normalize internally
    tools: StoredTool[] = [],
  ) {
    this.tools = new Map(tools.map(tool => [tool.name, tool]))
  }

  has(toolName: string) {
    return this.tools.has(toolName);
  }

  private getToolOrThrow(toolName: string): StoredTool {
    const tool = this.tools.get(toolName);
    if (!tool) {
      throw new Error(`Tool ${toolName} not found`);
    }
    return tool;
  }

  async invoke<TName extends string>(
    toolName: TName,
    rawArgs: unknown,
  ): Promise<unknown> {
    const tool = this.getToolOrThrow(toolName);
    const handler = tool.handler;
    const inputSchema = tool.schema;
    const outputSchema = tool.outputSchema;

    try {
      // Parse input args
      const inputResponse = await inputSchema.safeParseAsync(rawArgs);
      if (inputResponse.error) {
        const strError = z.prettifyError(inputResponse.error);
        throw new Error(`Tool ${toolName} returned invalid input: ${strError}`);
      }
      const args = inputResponse.data;

      // Call the handler
      const rawOutput = await handler(args);

      // Parse output
      const response = await outputSchema.safeParseAsync(rawOutput);
      if (response.error) {
        const strError = z.prettifyError(response.error);
        throw new Error(
          `Tool ${toolName} returned invalid output: ${strError}`,
        );
      }
      const output = response.data;
      return output;
    } catch (error) {
      return {
        status: "error",
        code: "TOOL_ERROR",
        message: error instanceof Error ? error.message : String(error),
        suggestedFix: "Try again with valid arguments.",
        meta: {
          args: rawArgs,
        },
      };
    }
  }

  @Memoize()
  getToolSchemas(): FrontendToolDefinition[] {
    return [...this.tools.values()].map((tool) => ({
      name: tool.name,
      description: tool.description,
      parameters: z.toJSONSchema(tool.schema),
      source: "frontend",
      mode: tool.mode,
    }));
  }
}

export const FRONTEND_TOOL_REGISTRY = new FrontendToolRegistry([
  testFrontendTool,
  // ADD MORE TOOLS HERE
]);
