/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { ensureSyntaxTree, syntaxTree } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { bench, describe, expect } from "vitest";
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
        ...options,
        setup() {
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

      bench(
        "one-character transaction (no view)",
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
        benchmarkOptions,
      );

      bench(
        "serialize entire document",
        () => {
          state.doc.toString();
        },
        benchmarkOptions,
      );

      bench(
        "reactive references / 1000 variables",
        () => {
          findReactiveVariables({ state, cellId: id, variables });
        },
        benchmarkOptions,
      );

      bench(
        "code lens declarations",
        () => {
          findDeclarationSites({ state, names });
        },
        benchmarkOptions,
      );

      bench(
        "cache scan / no cache sites",
        () => {
          findCacheSites(state);
        },
        benchmarkOptions,
      );
    });
  }
}
