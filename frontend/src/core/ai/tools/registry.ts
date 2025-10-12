/* Copyright 2024 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { Memoize } from "typescript-memoize";
import { type ZodObject, z } from "zod";
import { type AiTool, ToolExecutionError, type StatusValue } from "./base";
import { TestFrontendTool } from "./sample-tool";

export type AnyZodObject = ZodObject<z.ZodRawShape>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type StoredTool = AiTool<any, any>;

/** should be the same as marimo/_config/config.py > CopilotMode */

type ToolDefinition = components["schemas"]["ToolDefinition"];
export type CopilotMode = ToolDefinition["mode"][number];

export interface FrontendToolDefinition extends ToolDefinition {
  source: "frontend";
}

export class FrontendToolRegistry {
  /** All registered tools */
  private tools = new Map<string, StoredTool>();

  constructor(tools: StoredTool[] = []) {
    this.tools = new Map(tools.map((tool) => [tool.name, tool]));
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
      // Handle structured errors
      if (error instanceof ToolExecutionError) {
        // Do not include stack trace in the response
        // it will confuse the Agent/LLM
        const { status, code, message, isRetryable, suggestedFix, meta } = error;
        return {
          status,
          code,
          message,
          isRetryable,
          suggestedFix,
          meta,
        };
      }

      // Handle unknown/generic errors
      return {
        status: "error" as StatusValue,
        code: "TOOL_ERROR",
        message: error instanceof Error ? error.message : String(error),
        isRetryable: false,
        suggestedFix: "Check the error message and try again with valid arguments.",
        meta: {
          args: rawArgs,
          errorType: error?.constructor?.name ?? typeof error,
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
  ...(import.meta.env.DEV ? [new TestFrontendTool()] : []),
  // ADD MORE TOOLS HERE
]);
