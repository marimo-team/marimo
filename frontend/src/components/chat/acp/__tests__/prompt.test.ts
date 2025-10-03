/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getAgentPrompt } from "../prompt";

describe("getAgentPrompt", () => {
  it("should generate complete agent prompt with default filename", () => {
    const result = getAgentPrompt("test-notebook.py");

    expect(result).toMatchSnapshot();
  });
});
