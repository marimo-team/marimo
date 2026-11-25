/* Copyright 2026 Marimo. All rights reserved. */

import type { CellAnalysis } from "@marimo-team/client/protocol";
import { atom, type createStore } from "jotai";
import { cellId } from "@/__tests__/branded";
import { cell, document } from "@/core/notebook/document/__tests__/fixtures";
import { createNotebookReplica } from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";

export type AnalysisCells = Record<
  string,
  Partial<Pick<CellAnalysis, "defs" | "refs">>
>;

export function setNotebookAnalysis(
  store: ReturnType<typeof createStore>,
  cells: AnalysisCells,
) {
  const replica =
    store.get(activeNotebookReplicaAtom) ?? createNotebookReplica(store);
  const ids = Object.keys(cells).map(cellId);
  const base = document();
  const analyzedDocument = {
    revision: { ...base.revision, order: ids },
    cells: new Map(ids.map((id) => [id, cell(id, "")])),
  };
  const analysis = {
    notebook_id: analyzedDocument.revision.notebook_id,
    document_etag: analyzedDocument.revision.etag,
    cells: Object.fromEntries(
      Object.entries(cells).map(([id, names]) => [
        id,
        { defs: [], refs: [], diagnostics: [], ...names },
      ]),
    ),
  };
  const documentAtom = atom(analyzedDocument);
  store.set(activeNotebookReplicaAtom, {
    ...replica,
    analysisAtom: atom({
      freshness: "current" as const,
      analysis,
      document: analyzedDocument,
    }),
    documentAtom,
    shownDocumentAtom: documentAtom,
  });
}
