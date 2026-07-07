/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getReadonlyCodeDisplay } from "../readonly-code-display";

describe("getReadonlyCodeDisplay", () => {
  it("unwraps SQL cells to their inner query and marks them as sql", () => {
    const result = getReadonlyCodeDisplay(
      'my_table = mo.sql("""SELECT 1 AS id""")',
    );
    expect(result.language).toBe("sql");
    expect(result.code).toBe("SELECT 1 AS id");
  });

  it("unwraps f-string SQL cells", () => {
    const result = getReadonlyCodeDisplay(
      'my_table = mo.sql(f"""SELECT 1 AS id""")',
    );
    expect(result.language).toBe("sql");
    expect(result.code).toBe("SELECT 1 AS id");
  });

  it("leaves plain Python cells untouched", () => {
    const code = "x = 1 + 2\nprint(x)";
    const result = getReadonlyCodeDisplay(code);
    expect(result.language).toBe("python");
    expect(result.code).toBe(code);
  });

  it("leaves non-SQL cells (e.g. markdown) unchanged as python", () => {
    const code = 'mo.md("""## Heading""")';
    const result = getReadonlyCodeDisplay(code);
    expect(result.language).toBe("python");
    expect(result.code).toBe(code);
  });
});
