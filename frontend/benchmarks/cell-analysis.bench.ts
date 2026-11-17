/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { ensureSyntaxTree, syntaxTree } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { test, describe, expect } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import {
  findCacheSites,
  findDeclarationSites,
} from "@/core/codemirror/code-lens/analyzer";
import { findReactiveVariables } from "@/core/codemirror/reactive-references/analyzer";
import type { Variables } from "@/core/variables/types";

const options = { time: 500, warmupTime: 200, iterations: 100 };
const id = cellId("edited-cell");
const variables: Variables = {};
for (let i = 0; i < 1000; i++) {
  const name = variableName(`source_${i}`);
  variables[name] = { name, declaredBy: [cellId("other-cell")], usedBy: [id] };
}

for (const lines of [20, 200, 2000]) {
  for (const valid of [true, false]) {
    describe(`${lines} lines / ${valid ? "valid" : "unfinished"} Python`, () => {
      const code =
        Array.from(
          { length: lines },
          (_, i) => `value_${i} = source_${i % 1000} + ${i}`,
        ).join("\n") + (valid ? "" : "\nunfinished = (");
      const names = new Set(
        Array.from({ length: lines }, (_, i) => `value_${i}`),
      );
      let state: EditorState;

      const benchmarkOptions = {
        beforeAll() {
          state = EditorState.create({ doc: code, extensions: [python()] });
          // EditorState.create only parses a prefix for large documents. Without
          // this check, a fast benchmark can silently measure incomplete analysis.
          ensureSyntaxTree(state, state.doc.length, 5000);
          // Publish the parser's completed tree into the immutable state field.
          state = state.update({}).state;
          expect(syntaxTree(state).length).toBe(state.doc.length);
          expect(findDeclarationSites({ state, names })).toHaveLength(
            valid ? lines : 0,
          );
          expect(
            findReactiveVariables({ state, cellId: id, variables }),
          ).toHaveLength(valid ? lines : 0);
        },
      };

      test("one-character transaction (no view)", async ({ bench }) => {
        await bench(
          "one-character transaction (no view)",
          benchmarkOptions,
          () => {
            // Start from a fixed state to avoid accumulating text/history. Parsing
            // and view work scheduled after the transaction is not included.
            const next = state.update({
              changes: { from: Math.floor(code.length / 2), insert: "x" },
            }).state;
            if (next.doc.length !== code.length + 1) {
              throw new Error("Edit did not apply");
            }
          },
        ).run(options);
      });

      test("serialize entire document", async ({ bench }) => {
        await bench("serialize entire document", benchmarkOptions, () => {
          state.doc.toString();
        }).run(options);
      });

      test("reactive references / 1000 variables", async ({ bench }) => {
        await bench(
          "reactive references / 1000 variables",
          benchmarkOptions,
          () => {
            findReactiveVariables({ state, cellId: id, variables });
          },
        ).run(options);
      });

      test("code lens declarations", async ({ bench }) => {
        await bench("code lens declarations", benchmarkOptions, () => {
          findDeclarationSites({ state, names });
        }).run(options);
      });

      test("cache scan / no cache sites", async ({ bench }) => {
        await bench("cache scan / no cache sites", benchmarkOptions, () => {
          findCacheSites(state);
        }).run(options);
      });
    });
  }
}
