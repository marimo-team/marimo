/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  extractAllVariableNames,
  generateUniqueVariableName,
} from "../variable-names";

describe("extractAllVariableNames", () => {
  it("should extract simple variable assignments", () => {
    const code = `x = 1
y = 2
z = 3`;
    const variables = extractAllVariableNames([code]);
    expect(variables).toContain("x");
    expect(variables).toContain("y");
    expect(variables).toContain("z");
  });

  it("should extract variables with type annotations", () => {
    const code = `x: int = 1
y: str = "hello"`;
    const variables = extractAllVariableNames([code]);
    expect(variables).toContain("x");
    expect(variables).toContain("y");
  });

  it("should extract tuple unpacking", () => {
    const code = "x, y, z = (1, 2, 3)";
    const variables = extractAllVariableNames([code]);
    expect(variables).toContain("x");
    expect(variables).toContain("y");
    expect(variables).toContain("z");
  });

  it("should handle multiple code snippets", () => {
    const codes = ["x = 1", "y = 2", "z = 3"];
    const variables = extractAllVariableNames(codes);
    expect(variables).toContain("x");
    expect(variables).toContain("y");
    expect(variables).toContain("z");
  });

  it("should extract UI element assignments", () => {
    const code = `slider = mo.ui.slider(0, 10)
text = mo.ui.text()`;
    const variables = extractAllVariableNames([code]);
    expect(variables).toContain("slider");
    expect(variables).toContain("text");
  });

  it("should handle empty code", () => {
    const variables = extractAllVariableNames([""]);
    expect(variables.size).toBe(0);
  });

  it("should ignore non-assignment variables", () => {
    const code = `x = 1
print(y)
z = x + 2`;
    const variables = extractAllVariableNames([code]);
    expect(variables).toContain("x");
    expect(variables).toContain("z");
    expect(variables).not.toContain("y"); // y is used but not assigned
  });
});

describe("generateUniqueVariableName", () => {
  it("should return base name if not taken", () => {
    const existingNames = new Set(["x", "y", "z"]);
    const uniqueName = generateUniqueVariableName("slider", existingNames);
    expect(uniqueName).toBe("slider");
  });

  it("should append _2 if base name is taken", () => {
    const existingNames = new Set(["slider"]);
    const uniqueName = generateUniqueVariableName("slider", existingNames);
    expect(uniqueName).toBe("slider_2");
  });

  it("should increment number if multiple versions exist", () => {
    const existingNames = new Set(["slider", "slider_2", "slider_3"]);
    const uniqueName = generateUniqueVariableName("slider", existingNames);
    expect(uniqueName).toBe("slider_4");
  });

  it("should work with different base names", () => {
    const existingNames = new Set(["text", "text_2"]);
    expect(generateUniqueVariableName("text", existingNames)).toBe("text_3");
    expect(generateUniqueVariableName("number", existingNames)).toBe("number");
  });

  it("should handle empty existing names", () => {
    const existingNames = new Set<string>();
    const uniqueName = generateUniqueVariableName("slider", existingNames);
    expect(uniqueName).toBe("slider");
  });

  it("should handle gaps in numbering", () => {
    const existingNames = new Set(["slider", "slider_3", "slider_5"]);
    const uniqueName = generateUniqueVariableName("slider", existingNames);
    expect(uniqueName).toBe("slider_2"); // fills the first gap
  });
});
