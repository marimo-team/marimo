/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, test } from "vitest";
import { createCellAtom, deleteCellsAtom } from "@/core/cells/actions";
import { moveCellAtom } from "@/core/cells/arrange";
import { cellIdsAtom, notebookAtom } from "@/core/cells/cells";
import { applyDocument } from "@/core/cells/document";
import type { CellId } from "@/core/cells/ids";
import { deriveLayout, layoutAtom } from "@/core/cells/layout";
import { notebookRunReason } from "@/core/cells/utils";
import {
  cellExecutionInputsAtom,
  cellExecutionView,
  cellFreshnessAtom,
  cellOutlineAtom,
  cellOutputInputsAtom,
  cellOutputsView,
} from "@/core/executions";
import { freshnessOf } from "@/core/executions/freshness";
import { queuedOrRunningCount } from "@/core/executions/select";
import { toChanges, viewDocument } from "@/core/notebook/document/draft";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { invariant } from "@/utils/invariant";
import {
  analysisEvent,
  CODE,
  cellIdOf,
  cellRecord,
  createHarness,
  documentEvent,
  execution,
  executionIdOf,
  type Harness,
  lifecycle,
  reducer,
  runAll,
  snapshot,
  type Store,
  validate,
} from "./large-notebook-state.fixture";

const fast = { time: 500, warmupTime: 100, iterations: 20 };
const slow = { time: 0, warmupTime: 0, warmupIterations: 1, iterations: 5 };
const once = { ...slow, warmupIterations: 0, iterations: 1 };
// Each sample adds an undo entry, so the sample count is fixed.
const structural = { ...slow, warmupIterations: 5, iterations: 50 };

for (const count of [500, 2000]) {
  // A 2,000-cell session takes seconds to set up, more on a busy machine.
  describe(
    `${count} cells / half hidden markdown`,
    { timeout: 600_000 },
    () => {
      const target = cellIdOf(count - 2);

      describe("load", () => {
        const events = snapshot(count);
        test("snapshot, validation only", async ({ bench }) => {
          await bench("snapshot, validation only", () => validate(events)).run(
            slow,
          );
        });

        test("snapshot, reducer only", async ({ bench }) => {
          const parsed = await validate(events);
          await bench("snapshot, reducer only", () => {
            parsed.reduce(reducer.reduce, reducer.initial);
          }).run(slow);
        });
      });

      describe("typing", () => {
        let harness: Harness;
        let iteration = 0;
        const lifecycleOptions = {
          async beforeAll() {
            harness = await createHarness(count, "per-event");
          },
          afterAll: () => harness.stop(),
        };

        test("one keystroke", async ({ bench }) => {
          await bench("one keystroke", lifecycleOptions, () => {
            const code = `${CODE}\n# ${iteration++ % 2}`;
            harness.store.set(harness.model.editAtom, (tx) =>
              tx.setCode(target, code),
            );
          }).run(fast);
        });

        test("one confirmed edit", async ({ bench }) => {
          let version = 1;
          await bench("one confirmed edit", lifecycleOptions, () => {
            version += 1;
            harness.send([
              {
                event: "cell",
                data: {
                  cell: cellRecord(count - 2, `${CODE}\n# ${version}`, version),
                },
              },
              documentEvent(count, version),
              analysisEvent(count, version),
            ]);
          }).run(fast);
        });
      });

      describe("typing, by step", () => {
        let harness: Harness;
        const lifecycleOptions = {
          async beforeAll() {
            harness = await createHarness(count, "per-event", {
              mounted: false,
            });
          },
          afterAll: () => harness.stop(),
        };
        const confirmed = () => {
          const replica = harness.store.get(activeNotebookReplicaAtom);
          const current = replica && harness.store.get(replica.documentAtom);
          invariant(current, "Expected a confirmed document");
          return current;
        };
        const draft = {
          cells: new Map([
            [target, { kind: "edit" as const, edit: { code: `${CODE}\n# 1` } }],
          ]),
          order: null,
        };

        test("viewDocument", async ({ bench }) => {
          await bench("viewDocument", lifecycleOptions, () => {
            viewDocument(confirmed(), draft);
          }).run(fast);
        });

        test("toChanges", async ({ bench }) => {
          await bench("toChanges", lifecycleOptions, () => {
            toChanges(confirmed(), draft);
          }).run(fast);
        });

        test("applyDocument", async ({ bench }) => {
          let view: ReturnType<typeof viewDocument>;
          await bench(
            "applyDocument",
            {
              async beforeAll() {
                await lifecycleOptions.beforeAll();
                view = viewDocument(confirmed(), draft);
              },
              afterAll: lifecycleOptions.afterAll,
            },
            () => {
              applyDocument(harness.store.get(notebookAtom), view);
            },
          ).run(fast);
        });
      });

      describe("kernel events", () => {
        for (const mode of ["per-event", "batched"] as const) {
          let harness: Harness;
          let run = 0;
          const lifecycleOptions = {
            async beforeAll() {
              harness = await createHarness(count, mode);
              run = 0;
            },
            afterAll: () => harness.stop(),
          };

          test(`one cell runs, ${mode}`, async ({ bench }) => {
            await bench(`one cell runs, ${mode}`, lifecycleOptions, () => {
              run += 1;
              harness.send([
                {
                  event: "execution.removed",
                  data: { id: executionIdOf(run - 1, count - 1) },
                },
                execution(run, count - 1, { status: "queued" }),
                ...lifecycle(run, count - 1, 0),
              ]);
            }).run(fast);
          });

          // One store update per event is quadratic: a sample takes tens of
          // seconds at 500 cells and minutes at 2,000.
          test.skipIf(mode === "per-event" && count > 500)(
            `every cell runs, ${mode}`,
            async ({ bench }) => {
              await bench(`every cell runs, ${mode}`, lifecycleOptions, () => {
                run += 1;
                harness.send(runAll(count, run));
              }).run(mode === "per-event" ? once : slow);
            },
          );
        }

        test("every cell runs, reducer only", async ({ bench }) => {
          const second = runAll(count, 1);
          const parsed = await validate([
            ...snapshot(count),
            ...runAll(count, 0),
            ...second,
          ]);
          const before = parsed
            .slice(0, -second.length)
            .reduce(reducer.reduce, reducer.initial);
          await bench("every cell runs, reducer only", () => {
            parsed.slice(-second.length).reduce(reducer.reduce, before);
          }).run(slow);
        });
      });

      describe("selectors", () => {
        let harness: Harness;
        const lifecycleOptions = {
          async beforeAll() {
            harness = await createHarness(count, "per-event", {
              mounted: false,
            });
          },
          afterAll: () => harness.stop(),
        };
        const selectors: Record<string, (store: Store) => unknown> = {
          "cellExecutionView for every cell": (store) => {
            const inputs = store.get(cellExecutionInputsAtom);
            return store
              .get(cellIdsAtom)
              .map((id) => cellExecutionView(inputs, id));
          },
          "freshness for every cell": (store) => {
            const { executions, results, cells } = store.get(
              cellExecutionInputsAtom,
            );
            const lookup = freshnessOf({
              executions,
              results,
              cells: cells as ReadonlyMap<Protocol.CellId, Protocol.Cell>,
            });
            return store.get(cellIdsAtom).map((id) => lookup(id));
          },
          cellOutputsView: (store) =>
            cellOutputsView(store.get(cellOutputInputsAtom)),
          notebookRunReason: (store) =>
            notebookRunReason(
              store.get(notebookAtom),
              store.get(cellExecutionInputsAtom),
              store.get(cellFreshnessAtom),
            ),
          queuedOrRunningCount: (store) =>
            queuedOrRunningCount(store.get(cellExecutionInputsAtom)),
          deriveLayout: (store) =>
            deriveLayout(
              [
                {
                  id: store.get(layoutAtom).columns[0].id,
                  ids: store.get(cellIdsAtom),
                },
              ],
              (id) => store.get(cellOutlineAtom(id)),
              new Set(),
            ),
        };

        for (const [name, select] of Object.entries(selectors)) {
          test(`${name}`, async ({ bench }) => {
            await bench(name, lifecycleOptions, () => {
              select(harness.store);
            }).run(fast);
          });
        }
      });

      describe("structure", () => {
        let harness: Harness;
        const lifecycleOptions = {
          async beforeAll() {
            harness = await createHarness(count, "per-event");
          },
          afterAll: () => harness.stop(),
        };
        const first = cellIdOf(1) as CellId;

        test("create and delete a cell at the top", async ({ bench }) => {
          await bench(
            "create and delete a cell at the top",
            lifecycleOptions,
            () => {
              const id = harness.store.set(createCellAtom, {
                before: first,
                focus: false,
              });
              invariant(id, "Expected a created cell");
              harness.store.set(deleteCellsAtom, { cellIds: [id] });
            },
          ).run(structural);
        });

        test("move the top cell down and up", async ({ bench }) => {
          await bench("move the top cell down and up", lifecycleOptions, () => {
            harness.store.set(moveCellAtom, { cellId: first, before: false });
            harness.store.set(moveCellAtom, { cellId: first, before: true });
          }).run(structural);
        });
      });
    },
  );
}
