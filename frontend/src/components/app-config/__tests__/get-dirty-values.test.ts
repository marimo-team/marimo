/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, test } from "vitest";
import { getDirtyValues } from "../user-config-form";

describe("getDirtyValues", () => {
  test("extracts only dirty fields", () => {
    const values = {
      display: { theme: "dark", fontSize: 14 },
      runtime: { dotenv: [".env.dev"], auto_reload: "lazy" },
    };
    const dirtyFields = {
      display: { theme: true },
    };

    const result = getDirtyValues(values, dirtyFields);

    expect(result).toEqual({ display: { theme: "dark" } });
    expect(result).not.toHaveProperty("runtime");
  });

  test("returns empty object when nothing is dirty", () => {
    const values = { display: { theme: "dark" } };
    const dirtyFields = {};

    const result = getDirtyValues(values, dirtyFields);

    expect(result).toEqual({});
  });

  test("handles nested dirty fields", () => {
    const values = {
      runtime: { auto_reload: "lazy", dotenv: [".env"] },
      display: { theme: "dark" },
    };
    const dirtyFields = {
      runtime: { auto_reload: true },
    };

    const result = getDirtyValues(values, dirtyFields);

    expect(result).toEqual({ runtime: { auto_reload: "lazy" } });
    expect(result.runtime).not.toHaveProperty("dotenv");
  });

  test("handles multiple dirty fields at same level", () => {
    const values = {
      display: { theme: "dark", fontSize: 16, width: "full" },
    };
    const dirtyFields = {
      display: { theme: true, fontSize: true },
    };

    const result = getDirtyValues(values, dirtyFields);

    expect(result).toEqual({ display: { theme: "dark", fontSize: 16 } });
    expect(result.display).not.toHaveProperty("width");
  });

  test("preserves unmodified runtime settings like dotenv", () => {
    const values = {
      display: { theme: "dark" },
      runtime: { dotenv: [".env.local"], pythonpath: ["/custom/path"] },
    };
    const dirtyFields = {
      display: { theme: true },
    };

    const result = getDirtyValues(values, dirtyFields);

    expect(result).toEqual({ display: { theme: "dark" } });
    expect(result).not.toHaveProperty("runtime");
  });
});
