/* Copyright 2024 Marimo. All rights reserved. */

import { type ZodObject, z } from "zod";
import type { BaseTool } from "./base";
import { testFrontendTool } from "./sample-tool";

export type AnyZodObject = ZodObject<z.ZodRawShape>;

interface StoredTool {
  /** Generic type for to avoid type errors */
  name: string;
  description: string;
  schema: AnyZodObject;
  outputSchema: AnyZodObject;
  mode: CopilotMode[];
  handler: (args: unknown) => Promise<unknown>;
}

/** should be the same as marimo/_config/config.py > CopilotMode */
export type CopilotMode = "manual" | "ask";

export interface FrontendToolDefinition {
  /** should be the same as marimo/_server/ai/tools/types.py > ToolDefinition */
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  source: "frontend";
  mode: CopilotMode[];
}
  
export class FrontendToolRegistry {
  /** All registered tools */
  private tools = new Map<string, StoredTool>();

  registerAll<TIn extends AnyZodObject, TOut extends AnyZodObject>(tools: BaseTool<TIn, TOut>[]) {
    tools.forEach((tool) => {
      this.register(tool);
    });
  }

  private register<TIn extends AnyZodObject, TOut extends AnyZodObject>(
    tool: BaseTool<TIn, TOut>,
  ) {
    // Make type generic to avoid type errors
    // Let invoke() handle runtime type checking
    const stored: StoredTool = {
      name: tool.name,
      description: tool.description,
      schema: tool.schema,
      outputSchema: tool.outputSchema,
      mode: tool.mode,
      handler: tool.handler as (args: unknown) => Promise<unknown>,
    };
    this.tools.set(tool.name, stored);
  }

  has(toolName: string) {
    return this.tools.has(toolName);
  }

  private getTool(toolName: string): StoredTool {
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
    const tool = this.getTool(toolName);
    const handler = tool.handler;
    const inputSchema = tool.schema;
    const outputSchema = tool.outputSchema;

    try{
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
        throw new Error(`Tool ${toolName} returned invalid output: ${strError}`);
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

export const FRONTEND_TOOL_REGISTRY = new FrontendToolRegistry();

/* Register all the frontend tools */
FRONTEND_TOOL_REGISTRY.registerAll([
  testFrontendTool,
  // ADD MORE TOOLS HERE
]);
