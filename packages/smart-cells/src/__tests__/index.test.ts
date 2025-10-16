import { expect, it } from "vitest";

import * as index from "../index.js";

it("index.ts should export the correct modules", () => {
  expect(Object.keys(index)).toMatchInlineSnapshot(`
    [
      "MarkdownParser",
      "PythonParser",
      "SQLParser",
    ]
  `);
});
