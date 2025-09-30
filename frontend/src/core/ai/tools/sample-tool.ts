/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type { BaseTool } from "./base";
import type { CopilotMode } from "./registry";

const schema = z.object({ name: z.string() });
const outputSchema = z.object({ message: z.string() });

const description = `
Test frontend tool that returns a greeting message.

Args:
- name (string): The name to include in the greeting.

Returns:
- { message: string } — The greeting message, e.g., "Hello: Alice".
`;

/** A sample frontend tool that returns "hello world" */
export class TestFrontendTool
  implements BaseTool<typeof schema, typeof outputSchema>
{
  public readonly name = "test_frontend_tool";
  public readonly description = description;
  public readonly schema = schema;
  public readonly outputSchema = outputSchema;
  public readonly mode: CopilotMode[] = ["ask"];

  public async handler({ name }: z.infer<typeof schema>) {
    return { message: `Hello: ${name}` };
  }
}

export const testFrontendTool = new TestFrontendTool();
