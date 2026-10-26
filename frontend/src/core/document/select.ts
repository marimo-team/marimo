/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { dequal } from "dequal";
import type { Atom } from "jotai/vanilla";
import { selectAtom } from "jotai/vanilla/utils";
import { type EditableCell, type EditableDocument, sameCell } from "./draft";

/**
 * Select one cell of a document.
 *
 * The atom notifies when the cell's code, name, or config changes. A new host
 * record with the same values leaves it unchanged. Each call creates an atom,
 * so keep it for as long as its subscription.
 */
export function selectCell(
  document: Atom<EditableDocument | null>,
  id: Protocol.CellId,
): Atom<EditableCell | undefined> {
  return selectAtom(
    document,
    (value) => value?.cells.get(id),
    (a, b) => a === b || (a !== undefined && b !== undefined && sameCell(a, b)),
  );
}

/** Select a document's cell order, null while the document is unavailable. */
export function selectOrder(
  document: Atom<EditableDocument | null>,
): Atom<readonly Protocol.CellId[] | null> {
  return selectAtom(document, (value) => value?.order ?? null, dequal);
}
