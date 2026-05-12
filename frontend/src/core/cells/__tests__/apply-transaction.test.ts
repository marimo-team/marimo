/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Tests for fromDocumentChanges / applyTransactionChanges in isolation.
 *
 * These test the change→action mapping for edge cases and error paths that
 * can't be exercised via the round-trip tests (since toDocumentChanges would
 * never produce malformed or conflicting changes). Basic correctness is
 * covered by document-roundtrip.test.ts. This file focuses on:
 *
 * - Multi-change transactions (create+move, create+set-code, set-code+delete)
 * - Cancelled changes (create+delete same cell)
 * - Missing/nonexistent anchors and cells
 * - Config propagation on create-cell (disabled, column)
 */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { MultiColumn } from "@/utils/id-tree";
import { exportedForTesting, type NotebookState } from "../cells";
import {
  applyTransactionChanges,
  exportedForTesting as middlewareExports,
} from "../document-changes";
import { CellId } from "../ids";

const { initialNotebookState, reducer, createActions } = exportedForTesting;

function createEditor(code: string) {
  const state = EditorState.create({
    doc: code,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId: "cell1" as CellId,
        completionConfig: {
          activate_on_typing: true,
          signature_hint_on_typing: false,
          copilot: false,
          codeium_api_key: null,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
        lspConfig: {},
      }),
    ],
  });
  return new EditorView({ state, parent: document.body });
}

let state: NotebookState;
let actions: ReturnType<typeof createActions>;

function setup(...codes: string[]) {
  state = initialNotebookState();
  state.cellIds = MultiColumn.from([]);
  actions = createActions((action) => {
    state = reducer(state, action);
    for (const [cellId, handle] of Object.entries(state.cellHandles)) {
      if (!handle.current) {
        const view = createEditor(state.cellData[cellId as CellId].code);
        const h: CellHandle = { editorView: view, editorViewOrNull: view };
        state.cellHandles[cellId as CellId] = { current: h };
      }
    }
  });
  for (const code of codes) {
    actions.createNewCell({ cellId: "__end__", before: false, code });
  }
}

afterEach(() => {
  middlewareExports.cancelPendingChanges();
});

function apply(changes: Parameters<typeof applyTransactionChanges>[0]) {
  applyTransactionChanges(changes, actions, () => state.cellIds.inOrderIds);
}

/** Snapshot of document state: ordering, code, name, config. */
function pretty(s: NotebookState): string {
  const lines = s.cellIds.inOrderIds.map((id) => {
    const cell = s.cellData[id];
    const flags: string[] = [];
    if (cell.name && cell.name !== "_") {
      flags.push(`name=${cell.name}`);
    }
    if (cell.config.hide_code) {
      flags.push("hide_code");
    }
    if (cell.config.disabled) {
      flags.push("disabled");
    }
    if (cell.config.column != null) {
      flags.push(`col=${cell.config.column}`);
    }
    const suffix = flags.length > 0 ? ` [${flags.join(", ")}]` : "";
    return `${id}: '${cell.code}'${suffix}`;
  });
  return `\n${lines.join("\n")}\n`;
}

/** Snapshot showing the physical column grouping in the MultiColumn tree. */
function prettyColumns(s: NotebookState): string {
  const lines = s.cellIds
    .getColumns()
    .map((col, idx) => `col${idx}: [${col.inOrderIds.join(", ")}]`);
  return `\n${lines.join("\n")}\n`;
}

let i = 0;

beforeAll(() => {
  CellId.create = () => `${i++}` as CellId;
});

beforeEach(() => {
  i = 0;
});

describe("applyTransactionChanges edge cases", () => {
  it("create-cell applies disabled and column config", () => {
    setup("a");
    apply([
      {
        type: "create-cell",
        cellId: cellId("new-cell"),
        code: "configured",
        name: "",
        config: { hide_code: true, disabled: true, column: 1 },
      },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      new-cell: 'configured' [hide_code, disabled, col=1]
      "
    `);
    // The new cell must physically land in the second column, not just
    // carry col=1 as stale metadata.
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0]
      col1: [new-cell]
      "
    `);
  });

  it("create-cell then move-cell in same transaction", () => {
    setup("a", "b");
    const [a] = state.cellIds.inOrderIds;
    apply([
      {
        type: "create-cell",
        cellId: cellId("new-cell"),
        code: "new",
        name: "",
        config: {},
      },
      { type: "move-cell", cellId: cellId("new-cell"), before: a },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      new-cell: 'new'
      0: 'a'
      1: 'b'
      "
    `);
  });

  it("create-cell then set-code in same transaction", () => {
    setup("a");
    apply([
      {
        type: "create-cell",
        cellId: cellId("new-cell"),
        code: "initial",
        name: "",
        config: {},
      },
      { type: "set-code", cellId: cellId("new-cell"), code: "updated" },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      new-cell: 'updated'
      "
    `);
  });

  it("create-cell then delete-cell same cell cancels out", () => {
    setup("a");
    apply([
      {
        type: "create-cell",
        cellId: cellId("ephemeral"),
        code: "tmp",
        name: "",
        config: {},
      },
      { type: "delete-cell", cellId: cellId("ephemeral") },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      "
    `);
  });

  it("multiple changes in one transaction", () => {
    setup("a", "b", "c");
    const [a, b, c] = state.cellIds.inOrderIds;
    apply([
      { type: "set-code", cellId: a, code: "x = 1" },
      { type: "set-name", cellId: b, name: "middle" },
      { type: "delete-cell", cellId: c },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1'
      1: 'b' [name=middle]
      "
    `);
  });

  it("move-cell with no anchor appends to end", () => {
    setup("a", "b", "c");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "move-cell", cellId: a }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      1: 'b'
      2: 'c'
      0: 'a'
      "
    `);
  });

  it("move-cell with missing after anchor falls back to end", () => {
    setup("a", "b");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "move-cell", cellId: a, after: cellId("nonexistent") }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      1: 'b'
      0: 'a'
      "
    `);
  });

  it("move-cell with missing before anchor falls back to start", () => {
    setup("a", "b");
    const [, b] = state.cellIds.inOrderIds;
    apply([{ type: "move-cell", cellId: b, before: cellId("nonexistent") }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      1: 'b'
      0: 'a'
      "
    `);
  });

  it("move-cell on nonexistent cell is a no-op", () => {
    setup("a", "b");
    apply([
      {
        type: "move-cell",
        cellId: cellId("nonexistent"),
        after: cellId("0"),
      },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'b'
      "
    `);
  });

  it("delete-cell for nonexistent cell does not crash subsequent changes", () => {
    setup("a", "b", "c");
    const [, b] = state.cellIds.inOrderIds;
    // Simulate the scenario from the bug report: a delete-cell for a cell ID
    // that was never added to the frontend, followed by a create-cell and
    // a set-code update.  The delete should be silently skipped, and the rest
    // of the transaction should still apply.
    apply([
      { type: "delete-cell", cellId: cellId("nonexistent") },
      {
        type: "create-cell",
        cellId: cellId("VrZA"),
        code: "import altair as alt",
        name: "",
        config: { hide_code: true },
      },
      { type: "set-code", cellId: b, code: "updated" },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'updated'
      2: 'c'
      VrZA: 'import altair as alt' [hide_code]
      "
    `);
  });

  it("empty changes is a no-op", () => {
    setup("a", "b");
    apply([]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'b'
      "
    `);
  });

  it("set-code updates the mounted editor view's document", () => {
    // Existing tests only check cellData.code — this covers the editor
    // view side, so regressions in the reducer's imperative sync (or in
    // the CellEditor useEffect that backs it up) don't go unnoticed.
    setup('x = "BEFORE"');
    const [a] = state.cellIds.inOrderIds;
    const editorView = state.cellHandles[a].current?.editorViewOrNull;
    expect(editorView?.state.doc.toString()).toBe('x = "BEFORE"');

    apply([{ type: "set-code", cellId: a, code: 'x = "AFTER"' }]);

    expect(state.cellData[a].code).toBe('x = "AFTER"');
    expect(editorView?.state.doc.toString()).toBe('x = "AFTER"');
  });

  it("create-cell then set-code on same cell updates editor", () => {
    // Mirrors the code_mode flow that exposed marimo-pair#27: create_cell
    // in one batch, edit_cell in a second batch, each arriving as a
    // separate transaction.
    setup();
    apply([
      {
        type: "create-cell",
        cellId: cellId("repro"),
        code: 'x = "BEFORE"',
        name: "repro_bug",
        config: {},
      },
    ]);
    const editorView =
      state.cellHandles[cellId("repro")].current?.editorViewOrNull;
    expect(editorView?.state.doc.toString()).toBe('x = "BEFORE"');

    apply([
      { type: "set-code", cellId: cellId("repro"), code: 'x = "AFTER"' },
      { type: "reorder-cells", cellIds: [cellId("repro")] },
    ]);

    expect(state.cellData[cellId("repro")].code).toBe('x = "AFTER"');
    expect(editorView?.state.doc.toString()).toBe('x = "AFTER"');
  });
});

describe("applyTransactionChanges column rebuild", () => {
  it("boundary anchors: set-config on column boundaries splits cells into columns", () => {
    // The user's exact example. Server sends a reorder + set-config only on
    // the cells at column boundaries. The replica must infer that the cells
    // in between inherit the column of the preceding anchor.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
  });

  it("boundary anchors on reordered cells: order follows reorder-cells", () => {
    // Start from a single column, reorder the cells and split at c.
    // The rebuild must use the new flat order from reorder-cells so that
    // b ends up next to a (col 0) and d ends up next to c (col 1).
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [d, a, c, b] },
      {
        type: "set-config",
        cellId: d,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [3, 0]
      col1: [2, 1]
      "
    `);
  });

  it("three columns: inherits column through consecutive cells", () => {
    setup("a", "b", "c", "d", "e", "f");
    const [a, b, c, d, e, f] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d, e, f] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: e,
        column: 2,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      col2: [4, 5]
      "
    `);
  });

  it("every cell explicitly tagged with a column", () => {
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: b,
        column: 1,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: d,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    // a and c in col0; b and d in col1. Order within each column follows
    // the reorder-cells order.
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 2]
      col1: [1, 3]
      "
    `);
  });

  it("set-config without reorder-cells moves the cell to the new column", () => {
    setup("a", "b", "c");
    const [, b] = state.cellIds.inOrderIds;
    apply([
      {
        type: "set-config",
        cellId: b,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    // Without reorder-cells, the flat order comes from the current tree.
    // b gets explicit col=1; a and c stay with default null → follow the
    // previous cell's column (a → col0 because prev=0; c → col1 because
    // prev was just set to 1 by b).
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0]
      col1: [1, 2]
      "
    `);
  });

  it("no column change: set-config only touching other fields does not repartition", () => {
    setup("a", "b", "c");
    const [, b] = state.cellIds.inOrderIds;
    apply([
      {
        type: "set-config",
        cellId: b,
        column: null,
        disabled: false,
        hideCode: true,
      },
    ]);
    // All three cells remain in a single column. No rebuild triggered.
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1, 2]
      "
    `);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'b' [hide_code]
      2: 'c'
      "
    `);
  });

  it("no changes: empty transaction leaves column structure alone", () => {
    // Setup a multi-column state first
    setup("a", "b");
    const [a, b] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: b,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0]
      col1: [1]
      "
    `);
    // Now apply no changes — column structure should be preserved.
    apply([]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0]
      col1: [1]
      "
    `);
  });

  it("merging columns: set-config col=0 for everything collapses to one column", () => {
    // Start in a multi-column state.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
    // Now merge everything back to col 0.
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: c,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: d,
        column: 0,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1, 2, 3]
      "
    `);
  });

  it("create-cell with column places cell in correct column", () => {
    setup("a", "b");
    const [, b] = state.cellIds.inOrderIds;
    apply([
      {
        type: "create-cell",
        cellId: cellId("fresh"),
        code: "x",
        name: "",
        config: { column: 1 },
        after: b,
      },
    ]);
    // a and b are in col 0 (unchanged). The new cell is created at the end
    // with column=1, so it should land physically in col 1.
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [fresh]
      "
    `);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'b'
      fresh: 'x' [col=1]
      "
    `);
  });

  it("multi-change transaction with column + code + name updates", () => {
    setup("a", "b", "c");
    const [a, b, c] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c] },
      { type: "set-code", cellId: a, code: "x = 1" },
      { type: "set-name", cellId: b, name: "middle" },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: b,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0]
      col1: [1, 2]
      "
    `);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [col=0]
      1: 'b' [name=middle, col=1]
      2: 'c'
      "
    `);
  });

  it("cancelled create+delete does not trigger column rebuild", () => {
    setup("a", "b");
    apply([
      {
        type: "create-cell",
        cellId: cellId("ephemeral"),
        code: "tmp",
        name: "",
        config: { column: 1 },
      },
      { type: "delete-cell", cellId: cellId("ephemeral") },
    ]);
    // The create+delete cancel out. The column metadata on the cancelled
    // create-cell shouldn't cause a spurious column rebuild.
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      "
    `);
  });

  it("boundary-anchor convention: moving an anchor pulls non-anchored followers", () => {
    // This documents the boundary-anchor convention used by the server: only
    // cells at column boundaries carry an explicit column. Non-anchor cells
    // have config.column=null and inherit the column of the previous cell.
    // That means moving an anchor also moves its silent followers.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    // Split into two columns. Only a and c are anchors.
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
    // Move the c anchor to col 0. d has no explicit column so it follows c.
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: c,
        column: 0,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1, 2, 3]
      "
    `);
  });

  it("explicit anchors on followers: move anchor leaves explicitly-tagged follower behind", () => {
    // Contrast with the previous test: if d is explicitly tagged col=1,
    // moving c back to col 0 should leave d in col 1.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: d,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
    // Move c back to col 0. Because d has its own explicit column=1, it
    // does NOT follow c.
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: c,
        column: 0,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1, 2]
      col1: [3]
      "
    `);
  });

  it("set-config before reorder-cells: processing is sorted so set-config runs last", () => {
    // Defensive test: even if a transaction has set-config *before*
    // reorder-cells, the implementation must process reorder-cells first so
    // that the column rebuild sees the intended final flat order. This
    // matches the order the backend plans transactions in.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      // set-config appears FIRST in the transaction.
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
      // reorder-cells comes afterwards.
      { type: "reorder-cells", cellIds: [a, b, c, d] },
    ]);
    // Result must be identical to the canonical order:
    // the tree is reshaped first, then column metadata is applied.
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
  });

  it("set-config interleaved between other changes is still run last", () => {
    // Another ordering variant: set-config interleaved between set-code and
    // reorder-cells. Our sort must move set-config to the end regardless of
    // position, while preserving the relative order of the other changes.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      { type: "set-code", cellId: a, code: "x = 1" },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      { type: "set-name", cellId: d, name: "last" },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [col=0]
      1: 'b'
      2: 'c' [col=1]
      3: 'd' [name=last]
      "
    `);
  });

  it("reorder-cells alone (no column changes) preserves existing columns", () => {
    // Start in a two-column state.
    setup("a", "b", "c", "d");
    const [a, b, c, d] = state.cellIds.inOrderIds;
    apply([
      { type: "reorder-cells", cellIds: [a, b, c, d] },
      {
        type: "set-config",
        cellId: a,
        column: 0,
        disabled: false,
        hideCode: false,
      },
      {
        type: "set-config",
        cellId: c,
        column: 1,
        disabled: false,
        hideCode: false,
      },
    ]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [0, 1]
      col1: [2, 3]
      "
    `);
    // Now reorder without any column changes. The rebuild must NOT fire.
    // setCellIds with fromWithPreviousShape preserves the column assignments.
    apply([{ type: "reorder-cells", cellIds: [b, a, d, c] }]);
    expect(prettyColumns(state)).toMatchInlineSnapshot(`
      "
      col0: [1, 0]
      col1: [3, 2]
      "
    `);
  });
});
