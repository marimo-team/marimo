/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  EditorState,
  Transaction,
  type TransactionSpec,
} from "@codemirror/state";
import { type EditorView, keymap } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { formattingChangeEffect } from "../../format";
import { exportedForTesting } from "../extensions";
import { type CodemirrorCellActions, cellActionsState } from "../state";

const { cellKeymaps, shouldAutorunMarkdownUpdate } = exportedForTesting;

describe("cellKeymaps", () => {
  const keys = (hotkeys: OverridingHotkeyProvider) =>
    EditorState.create({
      extensions: cellKeymaps({ cellId: CellId.create(), hotkeys }),
    })
      .facet(keymap)
      .flat()
      .map((binding) => binding.key);

  it("binds merge only once the user sets a key", () => {
    expect(keys(new OverridingHotkeyProvider({}))).not.toContain("");
    expect(
      keys(
        new OverridingHotkeyProvider({ "cell.mergeCellBelow": "Alt-Shift-F9" }),
      ),
    ).toContainEqual(expect.stringMatching(/F9$/));
  });

  it("merges the cell when the bound key runs", () => {
    const cellId = CellId.create();
    const mergeCellBelow = vi.fn();
    const state = EditorState.create({
      extensions: [
        cellActionsState.of({
          mergeCellBelow,
        } as unknown as CodemirrorCellActions),
        cellKeymaps({
          cellId,
          hotkeys: new OverridingHotkeyProvider({
            "cell.mergeCellBelow": "Alt-Shift-F9",
          }),
        }),
      ],
    });
    const binding = state
      .facet(keymap)
      .flat()
      .find((b) => b.key?.endsWith("F9"));

    binding?.run?.({ state } as EditorView);

    expect(mergeCellBelow).toHaveBeenCalledWith({ cellId });
  });
});

function createTransaction(spec: TransactionSpec) {
  return EditorState.create({ doc: "" }).update(spec);
}

describe("shouldAutorunMarkdownUpdate", () => {
  it.each(["input.type", "delete.backward", "undo", "redo"])(
    "accepts local %s transactions",
    (userEvent) => {
      const transaction = createTransaction({
        changes: { from: 0, insert: "#" },
        annotations: [Transaction.userEvent.of(userEvent)],
      });

      expect(
        shouldAutorunMarkdownUpdate({
          docChanged: transaction.docChanged,
          transactions: [transaction],
        }),
      ).toBe(true);
    },
  );

  it("ignores formatting changes", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [Transaction.userEvent.of("input.type")],
      effects: [formattingChangeEffect.of(true)],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
      }),
    ).toBe(false);
  });

  it("ignores remote transactions while focused", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [Transaction.remote.of(true)],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
        hasFocus: true,
      }),
    ).toBe(false);
  });

  it("ignores programmatic doc changes without a user event", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
      }),
    ).toBe(false);
  });

  it("allows focused local doc changes without user event annotations", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
        hasFocus: true,
      }),
    ).toBe(true);
  });

  it("honors the predicate gate", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [Transaction.userEvent.of("input.type")],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
        predicate: () => false,
      }),
    ).toBe(false);
  });
});
