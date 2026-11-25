/* Copyright 2026 Marimo. All rights reserved. */
import { EditorState } from "@codemirror/state";
import { setCellCodeAtom } from "@/core/cells/actions";
import { ensureCellEditorView, getNotebook } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { languageAdapterFromCode } from "../language/extension";

export function getSearchDocuments() {
  const { cellIds, cellData, cellHandles } = getNotebook();
  return cellIds.map((cellId) => {
    const view = cellHandles[cellId]?.current?.editorViewOrNull;
    const adapter = languageAdapterFromCode(cellData[cellId].code);
    const [text, , metadata] = adapter.transformIn(cellData[cellId].code);
    return {
      key: view ?? cellId,
      view,
      state: view?.state ?? EditorState.create({ doc: text }),
      ensureView: () => ensureCellEditorView(cellId),
      replaceText: (code: string) =>
        store.set(setCellCodeAtom, {
          cellId,
          code: adapter.transformOut(code, metadata)[0],
        }),
    };
  });
}
