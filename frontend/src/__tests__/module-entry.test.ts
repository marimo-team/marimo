/* Copyright 2026 Marimo. All rights reserved. */

import { expect, it } from "vitest";
import { moduleEntry } from "../../lint/module-entry.js";

/** Whether the rule reports importing `source` from `file`. */
function reports(file: string, source: string): boolean {
  let reported = false;
  const visitors = moduleEntry.createOnce({
    filename: `/repo/frontend/src/${file}`,
    report: () => {
      reported = true;
    },
  });
  visitors.ImportDeclaration({ source: { value: source } });
  return reported;
}

it.each([
  ["components/editor.tsx", "@/core/notebook", false],
  ["components/editor.tsx", "@/core/notebook/attachments", true],
  ["core/notebook/index.ts", "./attachments", false],
  ["core/notebook/index.ts", "./document/hooks", true],
  ["core/session/active-notebook.ts", "@/core/notebook/replica", false],
  ["core/session/active-notebook.ts", "../notebook/replica", false],
  ["core/session/active-notebook.ts", "@/core/notebook/document", false],
  ["core/notebook/replica/replica.ts", "./resources/document", false],
  [
    "core/notebook/replica/replica.ts",
    "@/core/notebook/replica/backend",
    false,
  ],
  ["core/session/__tests__/a.test.ts", "../../notebook/replica/replica", false],
  ["core/session/fixtures.ts", "../notebook/replica/__tests__/fixtures", false],
  ["core/session/active-notebook.ts", "@/core/notebook/replica/replica", true],
  [
    "core/session/active-notebook.ts",
    "../notebook/replica/resources/document",
    true,
  ],
  ["core/session/active-notebook.ts", "../notebook/document/hooks", true],
])("from %s, importing %s reports %s", (file, source, expected) => {
  expect(reports(file, source)).toBe(expected);
});
