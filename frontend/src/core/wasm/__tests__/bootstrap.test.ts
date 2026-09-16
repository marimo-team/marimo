/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { requirementName } from "../worker/bootstrap";

describe("requirementName", () => {
  it("returns the distribution name for a bare requirement", () => {
    expect(requirementName("pandas")).toBe("pandas");
  });

  it.each([
    ["pandas==2.1.0", "pandas"],
    ["pandas>=2", "pandas"],
    ["pandas<=2", "pandas"],
    ["pandas~=2.1", "pandas"],
    ["pandas!=2.0", "pandas"],
    ["nltools===0.6.0.dev2", "nltools"],
  ])("cuts the specifier off %s", (requirement, expected) => {
    expect(requirementName(requirement)).toBe(expected);
  });

  it("cuts extras and markers", () => {
    expect(requirementName("rich[jupyter]>=13")).toBe("rich");
    expect(requirementName('cowsay==6.1; sys_platform == "emscripten"')).toBe(
      "cowsay",
    );
  });

  it("cuts a URL requirement at the name", () => {
    expect(requirementName("pkg @ https://example.com/pkg.whl")).toBe("pkg");
  });

  it("tolerates surrounding whitespace", () => {
    expect(requirementName("  pandas >= 2  ")).toBe("pandas");
  });
});
