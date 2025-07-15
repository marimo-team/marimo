/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { MarimoError } from "@/core/kernel/messages";
import { getAutoFixes, getImportCode } from "../errors";

describe("getImportCode", () => {
  it("returns simple import for same name", () => {
    expect(getImportCode("json")).toBe("import json");
    expect(getImportCode("math")).toBe("import math");
  });

  it("returns aliased import for different names", () => {
    expect(getImportCode("np")).toBe("import numpy as np");
    expect(getImportCode("pd")).toBe("import pandas as pd");
    expect(getImportCode("plt")).toBe("import matplotlib.pyplot as plt");
  });
});

describe("getAutoFixes", () => {
  it("returns wrap in function fix for multiple-defs error", () => {
    const error: MarimoError = {
      type: "multiple-defs",
      name: "foo",
      cells: ["foo"],
    };

    const fixes = getAutoFixes(error);
    expect(fixes).toHaveLength(1);
    expect(fixes[0].title).toBe("Fix: Wrap in a function");
  });

  it("returns import fix for NameError with known import", () => {
    const error: MarimoError = {
      type: "exception",
      exception_type: "NameError",
      msg: "name 'np' is not defined",
    };

    const fixes = getAutoFixes(error);
    expect(fixes).toHaveLength(1);
    expect(fixes[0].title).toBe("Fix: Add 'import numpy as np'");
  });

  it("returns no fixes for NameError with unknown import", () => {
    const error: MarimoError = {
      type: "exception",
      exception_type: "NameError",
      msg: "name 'unknown_module' is not defined",
    };

    expect(getAutoFixes(error)).toHaveLength(0);
  });

  it("returns no fixes for other error types", () => {
    const error: MarimoError = {
      type: "syntax",
      msg: "invalid syntax",
    };

    expect(getAutoFixes(error)).toHaveLength(0);
  });
});
