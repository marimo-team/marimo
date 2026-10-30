/* Copyright 2026 Marimo. All rights reserved. */

/** The active document model, as the notebook operations reach it. */

import type { Getter, Setter } from "jotai";
import type { DocumentModel, EditableDocument } from "@/core/notebook/document";
import { activeDocumentModelAtom } from "../session/active-notebook";
import { notebookAtom } from "./cells";
import type { CellId } from "./ids";

export function modelOf(get: Getter): DocumentModel {
  const model = get(activeDocumentModelAtom);
  if (!model) {
    throw new Error("The notebook has no document to edit");
  }
  return model;
}

export function documentOf(get: Getter): EditableDocument {
  const document = get(modelOf(get).documentAtom);
  if (!document) {
    throw new Error("The notebook has no document to edit");
  }
  return document;
}

/** Scroll to and focus the cell once it mounts. */
export function focusWhenMounted(set: Setter, cellId: CellId): void {
  set(notebookAtom, (state) => ({ ...state, scrollKey: cellId }));
}
