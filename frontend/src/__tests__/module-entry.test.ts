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
  ["core/websocket/state.ts", "@/core/host", false],
  ["core/websocket/state.ts", "../host", false],
  ["core/websocket/state.ts", "@/core/document", false],
  ["core/host/replica.ts", "./resources/document", false],
  ["core/host/replica.ts", "@/core/host/backend", false],
  ["core/websocket/__tests__/a.test.ts", "../../host/replica", false],
  ["core/websocket/fixtures.ts", "../host/__tests__/fixtures", false],
  ["core/websocket/state.ts", "@/core/host/replica", true],
  ["core/websocket/state.ts", "../host/resources/document", true],
  ["core/websocket/state.ts", "../document/hooks", true],
])("from %s, importing %s reports %s", (file, source, expected) => {
  expect(reports(file, source)).toBe(expected);
});
