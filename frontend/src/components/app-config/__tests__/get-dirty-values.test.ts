/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import type { FieldValues } from "react-hook-form";

/**
 * Extract only the values that have been modified (dirty) from form state.
 * Copy of the function from user-config-form.tsx for testing.
 */
function getDirtyValues<T extends FieldValues>(
  values: T,
  dirtyFields: Partial<Record<keyof T, unknown>>,
): Partial<T> {
  const result: Partial<T> = {};
  for (const key of Object.keys(dirtyFields) as Array<keyof T>) {
    const dirty = dirtyFields[key];
    if (dirty === true) {
      result[key] = values[key];
    } else if (typeof dirty === "object" && dirty !== null) {
      const nested = getDirtyValues(
        values[key] as FieldValues,
        dirty as Partial<Record<string, unknown>>,
      );
      if (Object.keys(nested).length > 0) {
        result[key] = nested as T[keyof T];
      }
    }
  }
  return result;
}

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
