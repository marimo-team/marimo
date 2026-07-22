/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { stripWrappingBackticks } from "../strip-wrapping-backticks";

// Cases aligned with `without_wrapping_backticks` on a complete string (single chunk).
const CASES: [string[], string][] = [
  [["Hello", " world", "!"], "Hello world!"],
  [["```", "print('hello')", "print('world')"], "print('hello')print('world')"],
  [
    ["print('hello')", "print('world')", "```"],
    "print('hello')print('world')```",
  ],
  [["```", "print('hello')", "```"], "print('hello')"],
  [["Hello", " ``` ", "world"], "Hello ``` world"],
  [["``", "`print('hello')", "``", "`"], "print('hello')"],
  [["``", "`", "\n", "print('hello')", "\n", "``", "`"], "print('hello')"],
  [
    ["```\n", "print('hello')", "print('world')", "\n```"],
    "print('hello')print('world')",
  ],
  [
    ["```\nprint('hello')\n", "print('world')\n```"],
    "print('hello')\nprint('world')",
  ],
  [
    ["```\n", "def test():\n    ", "return True\n```"],
    "def test():\n    return True",
  ],
  [[], ""],
  [["```idk```"], "idk"],
  [["Hello world"], "Hello world"],
  [
    ["```python\n", "def hello():\n    ", "print('world')\n```"],
    "def hello():\n    print('world')",
  ],
  [
    ["```python", "\ndef hello():\n    ", "print('world')\n```"],
    "def hello():\n    print('world')",
  ],
  [
    ["```sql", "SELECT * FROM table", " WHERE id = 1", "```"],
    "SELECT * FROM table WHERE id = 1",
  ],
  [
    ["```sql\n", "SELECT * FROM table\n", "WHERE id = 1\n```"],
    "SELECT * FROM table\nWHERE id = 1",
  ],
  [["```", "print('hello')", "```  "], "print('hello')  "],
  [["```python\n", "print('hello')", "\n``` "], "print('hello') "],
  [["```", "code", "```\t\n"], "code\t\n"],
  [["  ```", "code", "```"], "code"],
  [[" ```python\n", "code", "```"], "code"],
  [["\t```", "code", "```"], "code"],
  [["\n", "\n", "```\n", "code", "\n```\n"], "code\n"],
  [["\n", "\n", "```python\n", "code", "\n```\n"], "code\n"],
  [["\n``", "`python\n", "code", "\n```\n"], "code\n"],
  [["\n`", "`", "`python\n", "code", "\n```\n"], "code\n"],
  [["```python ", "code", "```"], " code"],
  [["```python\t", "code", "```"], "\tcode"],
  [["```\n", "```"], ""],
  [["```python\n", "```"], ""],
  [["```\n", "code"], "code"],
  [["```python\n", "code"], "code"],
  [["code", "\n```"], "code\n```"],
  [
    ["```\n", "x = 1\n", "```\n", "```\n", "y = 2\n", "```"],
    "x = 1\n```\n```\ny = 2",
  ],
  [["```python\n", "s = 'use `backticks`'\n", "```"], "s = 'use `backticks`'"],
  [["``", "`\n", "code\n", "``", "`"], "code"],
  [["```", "python\n", "code\n", "```"], "code"],
  [["```", "code", "```"], "code"],
  [["prefix ", "```\n", "code\n", "```"], "prefix ```\ncode\n```"],
  [["```\n", "code\n", "```", " suffix"], "code\n``` suffix"],
  [["```\n\n", "code\n\n", "```"], "\ncode\n"],
  [["```\n", "  code  \n", "```"], "  code  "],
  [["```\n", "\tcode\t\n", "```"], "\tcode\t"],
  [
    ["```\n", "x\n", "```\n", "```python\n", "y\n", "```"],
    "x\n```\n```python\ny",
  ],
  [["```javascript\n", "console.log()\n", "```"], "javascript\nconsole.log()"],
  [["```markdown\n", "# Title\n", "```"], "# Title"],
];

describe("stripWrappingBackticks", () => {
  it.each(CASES)("strips fences for %j", (chunks, expected) => {
    expect(stripWrappingBackticks(chunks.join(""))).toBe(expected);
  });
});

// In streaming mode, the opening fence is stripped as soon as it is
// unambiguous, but the closing fence is left untouched (it may not have
// arrived yet, or a trailing "```" may be content).
const STREAMING_CASES: [string, string][] = [
  // No fence: passthrough.
  ["import pandas as pd", "import pandas as pd"],
  // Plain opening fence stripped once the first line is terminated.
  ["```\n", ""],
  ["```\ncode", "code"],
  ["```\ncode\nmore", "code\nmore"],
  // Opening fence stripped, closing fence intentionally kept while streaming.
  ["```\ncode\n```", "code\n```"],
  ["```python\ncode\n```", "code\n```"],
  // Language fences stripped as soon as the full identifier is present.
  ["```python", ""],
  ["```python\n", ""],
  ["```python\ncode", "code"],
  ["```sql\nSELECT 1", "SELECT 1"],
  ["```markdown\n# Title", "# Title"],
  // Leading whitespace before the fence.
  ["  ```python\ncode", "code"],
  // Partial language identifiers are left intact until they resolve.
  ["```", "```"],
  ["```p", "```p"],
  ["```py", "```py"],
  ["```pyth", "```pyth"],
  ["```s", "```s"],
  ["```mark", "```mark"],
  // First-line content that is not a known language prefix is stripped as a
  // plain fence even before a newline arrives.
  ["```x", "x"],
  ["```x = 1", "x = 1"],
  // Unsupported language identifiers are kept as content (matches final mode).
  ["```json\ncode", "json\ncode"],
];

describe("stripWrappingBackticks (streaming)", () => {
  it.each(STREAMING_CASES)("strips opening fence for %j", (text, expected) => {
    expect(stripWrappingBackticks(text, { streaming: true })).toBe(expected);
  });
});
