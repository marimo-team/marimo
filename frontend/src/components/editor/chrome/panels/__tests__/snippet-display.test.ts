/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getSnippetDisplay } from "../snippet-display";

describe("getSnippetDisplay", () => {
  it("shows sql cells as the sql query", () => {
    const { language, value } = getSnippetDisplay(
      'df = mo.sql("""SELECT * FROM users LIMIT 5""")',
    );
    expect(language).toBe("sql");
    expect(value).toBe("SELECT * FROM users LIMIT 5");
  });

  it("keeps plain python cells as python", () => {
    const code = "x = 1 + 2\nprint(x)";
    expect(getSnippetDisplay(code)).toEqual({
      language: "python",
      value: code,
    });
  });
});
