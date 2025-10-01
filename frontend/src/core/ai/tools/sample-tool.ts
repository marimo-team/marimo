/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type { AiTool } from "./base";
import type { CopilotMode } from "./registry";

const description = `
Test frontend tool that returns a greeting message.

Args:
- name (string): The name to include in the greeting.

Returns:
- { message: string } — The greeting message, e.g., "Hello: Alice".
`;

interface Input {
  name: string;
}

interface Output {
  message: string;
}

/** A sample frontend tool that returns "hello world" */
export class TestFrontendTool implements AiTool<Input, Output> {
  readonly name = "test_frontend_tool";
  readonly description = description;
  readonly schema = z.object({ name: z.string() });
  readonly outputSchema = z.object({ message: z.string() });
  readonly mode: CopilotMode[] = ["ask"];

  async handler({ name }: Input) {
    return { message: `Hello: ${name}` };
  }
}
