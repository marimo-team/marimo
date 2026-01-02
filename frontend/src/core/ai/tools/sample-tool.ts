/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import {
  type AiTool,
  type ToolDescription,
  ToolExecutionError,
  type ToolOutputBase,
  toolOutputBaseSchema,
} from "./base";
import type { CopilotMode } from "./registry";

const description: ToolDescription = {
  baseDescription: "Test frontend tool that returns a greeting message.",
  additionalInfo: `
  Args:
    - name (string): The name to include in the greeting.

  Returns:
    - Output with data containing the greeting message.
  `,
};

interface Input {
  name: string;
}

interface GreetingData {
  greeting: string;
  timestamp: string;
}

interface Output extends ToolOutputBase {
  data: GreetingData;
}

/** A sample frontend tool that demonstrates real tool output structure */
export class TestFrontendTool implements AiTool<Input, Output> {
  readonly name = "test_frontend_tool";
  readonly description = description;
  readonly schema = z.object({ name: z.string() });
  readonly outputSchema = toolOutputBaseSchema.extend({
    data: z.object({
      greeting: z.string(),
      timestamp: z.string(),
    }),
  });
  readonly mode: CopilotMode[] = ["ask"];

  async handler({ name }: Input): Promise<Output> {
    // Example: Validate input and throw ToolExecutionError on invalid data
    if (!name.trim()) {
      throw new ToolExecutionError(
        "Name cannot be empty",
        "INVALID_INPUT",
        false,
        "Please provide a non-empty name",
        { field: "name", received: name },
      );
    }

    return {
      status: "success",
      data: {
        greeting: `Hello: ${name}`,
        timestamp: new Date().toISOString(),
      },
      next_steps: [
        "You can now proceed with your next task",
        "Try calling another tool if needed",
      ],
    };
  }
}
