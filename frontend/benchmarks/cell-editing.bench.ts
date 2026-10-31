/* Copyright 2026 Marimo. All rights reserved. */

import { type Atom, createStore } from "jotai";
import { test, describe, expect, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import {
  cellDataAtom,
  cellErrorsAtom,
  cellHandleAtom,
  cellIdToNamesMap,
  exportedForTesting,
  needsRunAtom,
  notebookAtom,
  notebookIsRunningAtom,
  notebookOutline,
  notebookQueuedOrRunningCountAtom,
  notebookReducer,
} from "@/core/cells/cells";
import type { CellData } from "@/core/cells/types";
import type { CellAction } from "@/core/cells/document-changes";
import { layoutStateAtom } from "@/core/layout/state";
import { lastSavedNotebookAtom, needsSaveAtom } from "@/core/saving/state";

// Keep action-to-document conversion, but exclude the network queue and timers.
// Otherwise a throughput benchmark queues millions of artificial keystrokes.
vi.mock("@/core/cells/document-changes", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/core/cells/document-changes")>();
  return {
    ...actual,
    documentTransactionMiddleware: actual.toDocumentChanges,
  };
});

const options = { time: 500, warmupTime: 200, iterations: 100 };
const code = Array.from({ length: 20 }, (_, i) => `value_${i} = ${i}`).join(
  "\n",
);

for (const count of [10, 25, 100, 1000]) {
  describe(`${count} cells / 20 lines each`, () => {
    for (const mode of [
      "reducer",
      "store",
      "cell subscribers",
      "derived subscribers",
    ] as const) {
      describe(`${mode}`, () => {
        const ids = Array.from({ length: count }, (_, i) =>
          cellId(`bench-${i}`),
        );
        const cellData: Record<string, Partial<CellData>> = {};
        for (const id of ids) {
          cellData[id] = { code, lastCodeRun: code };
        }
        let state = MockNotebook.notebookState({ cellData });
        const store = createStore();
        const unsubscribes: Array<() => void> = [];
        const target = ids[Math.floor(ids.length / 2)];
        let iteration = 0;

        function edit() {
          const action: CellAction = {
            type: "updateCellCode",
            payload: {
              cellId: target,
              code: `${code}\n# ${iteration++ % 2}`,
              formattingChange: false,
            },
          };
          if (mode === "reducer") {
            state = notebookReducer(state, action);
          } else {
            store.set(notebookAtom, (previous) =>
              notebookReducer(previous, action),
            );
          }
        }

        function setup() {
          state = MockNotebook.notebookState({ cellData });
          iteration = 0;
          store.set(notebookAtom, state);
          store.set(lastSavedNotebookAtom, {
            codes: ids.map(() => code),
            names: ids.map((id) => state.cellData[id].name),
            configs: ids.map((id) => state.cellData[id].config),
            layout: store.get(layoutStateAtom),
          });
          const subscribe = (value: Atom<unknown>) => {
            unsubscribes.push(store.sub(value, () => undefined));
          };
          if (mode === "cell subscribers" || mode === "derived subscribers") {
            for (const id of ids) {
              subscribe(cellDataAtom(id));
              subscribe(exportedForTesting.cellRuntimeAtom(id));
              subscribe(cellHandleAtom(id));
            }
          }
          if (mode === "derived subscribers") {
            for (const value of [
              cellErrorsAtom,
              notebookOutline,
              cellIdToNamesMap,
              notebookIsRunningAtom,
              notebookQueuedOrRunningCountAtom,
              needsRunAtom,
              needsSaveAtom,
            ]) {
              subscribe(value);
            }
          }

          // Verify the fixture really edits one cell, preserving unrelated data.
          const previous = state;
          edit();
          const next = mode === "reducer" ? state : store.get(notebookAtom);
          expect(next.cellData[target].code).toBe(`${code}\n# 0`);
          expect(next.cellData[ids[0]]).toBe(previous.cellData[ids[0]]);
          expect(next.cellRuntime).toBe(previous.cellRuntime);
        }

        function teardown() {
          for (const unsubscribe of unsubscribes) {
            unsubscribe();
          }
          unsubscribes.length = 0;
        }

        test("one edit", async ({ bench }) => {
          await bench(
            "one edit",
            { beforeAll: setup, afterAll: teardown },
            edit,
          ).run(options);
        });
      });
    }
  });
}
