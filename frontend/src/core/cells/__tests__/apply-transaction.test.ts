/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { MultiColumn } from "@/utils/id-tree";
import { applyTransactionOps } from "../apply-transaction";
import { exportedForTesting, type NotebookState } from "../cells";
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

function apply(ops: Parameters<typeof applyTransactionOps>[0]) {
  applyTransactionOps(
    ops,
    {
      createNewCell: actions.createNewCell,
      deleteCell: actions.deleteCell,
      setCellIds: actions.setCellIds,
      setCellCodes: actions.setCellCodes,
      updateCellName: actions.updateCellName,
      updateCellConfig: actions.updateCellConfig,
    },
    () => state.cellIds.inOrderIds,
  );
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

describe("applyTransactionOps", () => {
  it("set-code updates code", () => {
    setup("x = 1", "y = 2");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "set-code", cellId: a, code: "x = 42" }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 42'
      1: 'y = 2'
      "
    `);
  });

  it("set-name renames a cell", () => {
    setup("x = 1");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "set-name", cellId: a, name: "my_cell" }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [name=my_cell]
      "
    `);
  });

  it("delete-cell removes a cell", () => {
    setup("a", "b", "c");
    const [, b] = state.cellIds.inOrderIds;
    apply([{ type: "delete-cell", cellId: b }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      2: 'c'
      "
    `);
  });

  it("reorder-cells replaces full ordering", () => {
    setup("a", "b", "c");
    const [a, b, c] = state.cellIds.inOrderIds;
    apply([{ type: "reorder-cells", cellIds: [c, a, b] }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      2: 'c'
      0: 'a'
      1: 'b'
      "
    `);
  });

  it("move-cell after", () => {
    setup("a", "b", "c");
    const [a, , c] = state.cellIds.inOrderIds;
    apply([{ type: "move-cell", cellId: a, after: c }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      1: 'b'
      2: 'c'
      0: 'a'
      "
    `);
  });

  it("move-cell before", () => {
    setup("a", "b", "c");
    const [a, , c] = state.cellIds.inOrderIds;
    apply([{ type: "move-cell", cellId: c, before: a }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      2: 'c'
      0: 'a'
      1: 'b'
      "
    `);
  });

  it("set-config hide_code", () => {
    setup("x = 1");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "set-config", cellId: a, hideCode: true }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [hide_code]
      "
    `);
  });

  it("set-config disabled", () => {
    setup("x = 1");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "set-config", cellId: a, disabled: true }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [disabled]
      "
    `);
  });

  it("create-cell appends at end", () => {
    setup("a", "b");
    apply([
      {
        type: "create-cell",
        cellId: "new-cell",
        code: "c = 3",
        name: "my_new",
        config: {},
      },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'b'
      new-cell: 'c = 3' [name=my_new]
      "
    `);
  });

  it("create-cell with after positions correctly", () => {
    setup("a", "b", "c");
    const [a] = state.cellIds.inOrderIds;
    apply([
      {
        type: "create-cell",
        cellId: "new-cell",
        code: "inserted",
        name: "",
        config: {},
        after: a,
      },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      new-cell: 'inserted'
      1: 'b'
      2: 'c'
      "
    `);
  });

  it("create-cell with before positions correctly", () => {
    setup("a", "b", "c");
    const [, b] = state.cellIds.inOrderIds;
    apply([
      {
        type: "create-cell",
        cellId: "new-cell",
        code: "inserted",
        name: "",
        config: {},
        before: b,
      },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      new-cell: 'inserted'
      1: 'b'
      2: 'c'
      "
    `);
  });

  it("create-cell with hide_code config", () => {
    setup("a");
    apply([
      {
        type: "create-cell",
        cellId: "new-cell",
        code: "hidden",
        name: "",
        config: { hide_code: true },
      },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      new-cell: 'hidden' [hide_code]
      "
    `);
  });

  it("create-cell then move-cell in same transaction", () => {
    setup("a", "b");
    const [a] = state.cellIds.inOrderIds;
    apply([
      {
        type: "create-cell",
        cellId: "new-cell",
        code: "new",
        name: "",
        config: {},
      },
      { type: "move-cell", cellId: "new-cell", before: a },
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
        cellId: "new-cell",
        code: "initial",
        name: "",
        config: {},
      },
      { type: "set-code", cellId: "new-cell", code: "updated" },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      new-cell: 'updated'
      "
    `);
  });

  it("set-code then delete same cell", () => {
    setup("a", "b");
    const [a] = state.cellIds.inOrderIds;
    apply([
      { type: "set-code", cellId: a, code: "doomed" },
      { type: "delete-cell", cellId: a },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      1: 'b'
      "
    `);
  });

  it("multiple ops in one transaction", () => {
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

  it("code + reorder in one transaction", () => {
    setup("a", "b", "c");
    const [a, b, c] = state.cellIds.inOrderIds;
    apply([
      { type: "set-code", cellId: a, code: "first" },
      { type: "set-code", cellId: c, code: "last" },
      { type: "reorder-cells", cellIds: [c, b, a] },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      2: 'last'
      1: 'b'
      0: 'first'
      "
    `);
  });

  it("delete + set-code on different cells", () => {
    setup("a", "b", "c");
    const [, b, c] = state.cellIds.inOrderIds;
    apply([
      { type: "delete-cell", cellId: b },
      { type: "set-code", cellId: c, code: "updated" },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      2: 'updated'
      "
    `);
  });

  it("create-cell then delete-cell same cell cancels out", () => {
    setup("a");
    apply([
      {
        type: "create-cell",
        cellId: "ephemeral",
        code: "tmp",
        name: "",
        config: {},
      },
      { type: "delete-cell", cellId: "ephemeral" },
    ]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      "
    `);
  });

  it("set-config with column", () => {
    setup("x = 1");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "set-config", cellId: a, column: 2 }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [col=2]
      "
    `);
  });

  it("set-config with multiple fields", () => {
    setup("x = 1");
    const [a] = state.cellIds.inOrderIds;
    apply([{ type: "set-config", cellId: a, hideCode: true, disabled: true }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'x = 1' [hide_code, disabled]
      "
    `);
  });

  it("empty ops is a no-op", () => {
    setup("a", "b");
    apply([]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      1: 'b'
      "
    `);
  });

  it("set-code on nonexistent cell is a no-op", () => {
    setup("a");
    apply([{ type: "set-code", cellId: "missing" as CellId, code: "x" }]);
    expect(pretty(state)).toMatchInlineSnapshot(`
      "
      0: 'a'
      "
    `);
  });
});
