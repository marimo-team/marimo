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
