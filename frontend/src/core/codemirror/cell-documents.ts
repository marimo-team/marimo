/* Copyright 2026 Marimo. All rights reserved. */
import {
  type ChangeSpec,
  EditorState,
  type StateEffect,
} from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { setCellCodeAtom } from "@/core/cells/actions";
import {
  ensureCellEditorView,
  getNotebook,
  type NotebookState,
} from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import {
  getCellCode,
  parseCellCode,
  prepareCellCodeUpdate,
} from "./language/cell-code";

/**
 * A cell's text, whether or not it has an editor. Operations across the
 * notebook read and write documents so offscreen cells never need to build one.
 */
export interface CellDocument {
  cellId: CellId;
  /** The mounted editor, if the cell has one. */
  view: EditorView | null;
  /** The editor's state, or the state an editor would start from. */
  state: EditorState;
  /** The Python source the notebook stores for this cell. */
  code: string;
  /** Build the editor now. Reserved for explicit navigation or editing. */
  ensureView: () => EditorView | undefined;
  /** Apply changes to `state` and write the result back to the cell. */
  applyChanges: (changes: ChangeSpec, userEvent: string) => void;
}

type ParsedCode = ReturnType<typeof parseCellCode>;

const parsedByCell = new Map<CellId, { code: string; parsed: ParsedCode }>();

function parsedCodeOf(cellId: CellId, code: string): ParsedCode {
  const cached = parsedByCell.get(cellId);
  if (cached?.code === code) {
    return cached.parsed;
  }
  const parsed = parseCellCode(code);
  parsedByCell.set(cellId, { code, parsed });
  return parsed;
}

/** The documents of cells on the page, in notebook order. */
export function getCellDocuments(): CellDocument[] {
  const { cellIds, cellData, cellHandles } = getNotebook();
  const present = new Set(cellIds);
  for (const cellId of parsedByCell.keys()) {
    if (!present.has(cellId)) {
      parsedByCell.delete(cellId);
    }
  }

  const documents: CellDocument[] = [];
  for (const cellId of cellIds) {
    const handle = cellHandles[cellId]?.current;
    // A cell that is not on the page, such as one in a collapsed section, has
    // no editor to show a result in.
    if (!handle) {
      continue;
    }
    const view = handle.editorView;
    const source = cellData[cellId].code;
    const { adapter, text, metadata } = parsedCodeOf(cellId, source);
    const state = view?.state ?? EditorState.create({ doc: text });
    documents.push({
      cellId,
      view,
      state,
      code: view ? getCellCode(view.state) : source,
      ensureView: () => ensureCellEditorView(cellId),
      applyChanges: (changes, userEvent) => {
        if (view) {
          view.dispatch({ changes, userEvent });
          return;
        }
        const nextText = state.update({ changes }).state.doc.toString();
        writeCellCode(cellId, adapter.transformOut(nextText, metadata)[0]);
      },
    });
  }
  return documents;
}

/** A mounted editor's code is ahead of the notebook store while the user types. */
export function getCellPythonCode(
  cellId: CellId,
  notebook: NotebookState = getNotebook(),
): string {
  const view = notebook.cellHandles[cellId]?.current?.editorView;
  return view
    ? getCellCode(view.state)
    : (notebook.cellData[cellId]?.code ?? "");
}

/**
 * Write a cell's Python source. A mounted editor takes the update as an edit
 * so selection and history survive; otherwise the notebook document does.
 */
export function writeCellCode(
  cellId: CellId,
  code: string,
  options: {
    userEvent?: string;
    effects?: StateEffect<unknown>[];
    /** Let the language follow the new code, as for a freshly loaded cell. */
    initialize?: boolean;
  } = {},
): void {
  const { userEvent, effects, initialize } = options;
  const view = getNotebook().cellHandles[cellId]?.current?.editorView;
  if (!view) {
    if (getNotebook().cellData[cellId]?.code !== code) {
      store.set(setCellCodeAtom, { cellId, code });
    }
    return;
  }
  const update = prepareCellCodeUpdate(view.state, code, { initialize });
  if (update) {
    view.dispatch(update, { userEvent, effects });
  }
}
