/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { getImportCode } from "../errors";

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
