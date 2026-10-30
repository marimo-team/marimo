/* Copyright 2026 Marimo. All rights reserved. */

/** A store whose notebook follows a document model, as the session wires it. */

import { history } from "@codemirror/commands";
import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { mockDocumentModel } from "@/__mocks__/document";
import type { CellId } from "@/core/cells/ids";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import {
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { exportedForTesting, notebookAtom, notebookReducer } from "../cells";
import { followDocument } from "../document";
import { layoutAtom } from "../layout";

export function setupNotebook(
  stops: Array<() => void>,
  cells?: Record<string, Protocol.Cell | null>,
) {
  const store = createStore();
  store.set(notebookAtom, exportedForTesting.initialNotebookState());
  const { model, stop } = mockDocumentModel(
    store,
    cells ? withCells(documentOf(), cells) : documentOf(),
  );
  const controller = new AbortController();
  stops.push(stop, () => controller.abort());
  followDocument({
    store,
    model,
    reconcile: (document) =>
      store.set(notebookAtom, (state) =>
        notebookReducer(state, {
          type: "reconcileDocument",
          payload: document,
        }),
      ),
    signal: controller.signal,
  });
  return {
    store,
    model,
    order: () => store.get(notebookAtom).cellIds.inOrderIds,
    /** The cells of each column, as the page lays them out. */
    columns: () => store.get(layoutAtom).columns.map((column) => column.ids),
    notebook: () => store.get(notebookAtom),
    cellIn: (id: string) => store.get(model.documentAtom)?.cells.get(id),
    /** Give a cell an editor, as mounting it would, with a cell's language setup. */
    mountEditor: (id: string) => {
      const view = new EditorView({
        state: EditorState.create({
          doc: store.get(model.documentAtom)?.cells.get(id)?.code ?? "",
          extensions: [
            history(),
            python(),
            adaptiveLanguageConfiguration({
              cellId: id as CellId,
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
        }),
      });
      store.get(notebookAtom).cellHandles[id as never].current = {
        editorView: view,
        editorViewOrNull: view,
      };
      return view;
    },
    /** Give a cell's output a heading, as the kernel's outline would. */
    heading: (id: string, level: number) =>
      store.set(notebookAtom, (state) => ({
        ...state,
        cellRuntime: {
          ...state.cellRuntime,
          [id]: {
            ...state.cellRuntime[id as never],
            outline: { items: [{ name: `H${level}`, level, by: { id } }] },
          },
        },
      })),
    visible: () => store.get(layoutAtom).columns[0].visible,
    /** Apply a reducer action, as `useReducerActions()` does. */
    dispatch: (action: Parameters<typeof notebookReducer>[1]) =>
      store.set(notebookAtom, (state) => notebookReducer(state, action)),
  };
}
