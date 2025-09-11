/* Copyright 2025 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getAgentPrompt } from "../prompt";

describe("getAgentPrompt", () => {
  it("should generate complete agent prompt with default filename", () => {
    const prompt = "Help me create a data visualization";
    const result = getAgentPrompt(prompt, "test-notebook.py");

    expect(result).toMatchSnapshot();
  });
});
