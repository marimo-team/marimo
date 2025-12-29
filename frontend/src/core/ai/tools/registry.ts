/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { Memoize } from "typescript-memoize";
import { type ZodObject, z } from "zod";
import {
  type AiTool,
  ToolExecutionError,
  type ToolNotebookContext,
} from "./base";
import { EditNotebookTool } from "./edit-notebook-tool";
import { RunStaleCellsTool } from "./run-cells-tool";
import { formatToolDescription } from "./utils";

export type AnyZodObject = ZodObject<z.ZodRawShape>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type StoredTool = AiTool<any, any>;

interface InvokeResult<TName> {
  tool_name: TName;
  result: unknown;
  error: string | null;
}

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
    toolContext: ToolNotebookContext,
  ): Promise<InvokeResult<TName>> {
    const tool = this.getToolOrThrow(toolName);
    const handler = tool.handler;
    const inputSchema = tool.schema;
    const outputSchema = tool.outputSchema;

    try {
      // Parse input args
      const inputResponse = await inputSchema.safeParseAsync(rawArgs);
      if (inputResponse.error) {
        const strError = z.prettifyError(inputResponse.error);
        throw new ToolExecutionError(
          `Tool ${toolName} returned invalid input: ${strError}`,
          "INVALID_ARGUMENTS",
          true,
          "Please check the arguments and try again.",
        );
      }
      const args = inputResponse.data;

      // Call the handler
      const rawOutput = await handler(args, toolContext);

      // Parse output
      const response = await outputSchema.safeParseAsync(rawOutput);
      if (response.error) {
        const strError = z.prettifyError(response.error);
        throw new Error(
          `Tool ${toolName} returned invalid output: ${strError}`,
        );
      }
      const result = response.data;
      return {
        tool_name: toolName,
        result,
        error: null,
      };
    } catch (error) {
      // Handle structured errors
      if (error instanceof ToolExecutionError) {
        return {
          tool_name: toolName,
          result: null,
          error: error.toStructuredString(),
        };
      }

      // Handle unknown/generic errors
      const genericError = new ToolExecutionError(
        error instanceof Error ? error.message : String(error),
        "TOOL_ERROR",
        false,
        "Check the error message and try again with valid arguments.",
        {
          args: rawArgs,
          errorType: error?.constructor?.name ?? typeof error,
        },
      );
      return {
        tool_name: toolName,
        result: null,
        error: genericError.toStructuredString(),
      };
    }
  }

  @Memoize()
  getToolSchemas(mode: CopilotMode): FrontendToolDefinition[] {
    const tools = [...this.tools.values()].filter((tool) =>
      tool.mode.includes(mode),
    );
    return tools.map((tool) => ({
      name: tool.name,
      description: formatToolDescription(tool.description),
      parameters: z.toJSONSchema(tool.schema),
      source: "frontend",
      mode: tool.mode,
    }));
  }
}

export const FRONTEND_TOOL_REGISTRY = new FrontendToolRegistry([
  new EditNotebookTool(),
  new RunStaleCellsTool(),
]);
