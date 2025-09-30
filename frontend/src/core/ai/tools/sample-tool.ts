/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { BaseTool } from "./base";

const schema = z.object({ name: z.string() });
const outputSchema = z.object({ message: z.string() });

/** A sample frontend tool that returns "hello world" */
export class TestFrontendTool extends BaseTool<
  typeof schema,
  typeof outputSchema
> {
  constructor() {
    super({
      name: "test_frontend_tool",
      description:
        "A test frontend tool that returns hi with the name passed in",
      schema,
      outputSchema,
      mode: ["ask"],
    });
  }

  protected async handle({ name }: z.infer<typeof schema>) {
    return { message: `Hello: ${name}` };
  }
}

export const testFrontendTool = new TestFrontendTool();
