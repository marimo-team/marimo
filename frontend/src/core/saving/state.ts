/* Copyright 2026 Marimo. All rights reserved. */

/** Whether the notebook has changes the host has not written to its store. */

import { dequal as isEqual } from "dequal";
import { atom } from "jotai";
import { type LayoutState, layoutStateAtom } from "../layout/state";
import {
  activeDocumentModelAtom,
  confirmedDocumentAtom,
} from "../session/active-notebook";

/** The document version, which counts confirmed changes. Null without a document. */
export const documentVersionAtom = atom(
  (get) => get(confirmedDocumentAtom)?.revision.version ?? null,
);

/**
 * The layout as the file last had it. The host document does not carry
 * the layout file, so this client compares it itself until it does.
 */
export const savedLayoutAtom = atom<LayoutState | undefined>(undefined);

/**
 * Whether saving would change the file: the host's document differs from
 * what it last wrote, this client has edits the host has not confirmed,
 * or the layout changed. A document never written reports as unsaved.
 */
export const needsSaveAtom = atom((get) => {
  const document = get(confirmedDocumentAtom);
  if (document === null) {
    return false;
  }
  if (document.revision.etag !== document.revision.saved_etag) {
    return true;
  }
  const model = get(activeDocumentModelAtom);
  if (model !== null) {
    const { status } = get(model.syncStatusAtom);
    if (status !== "idle" && status !== "unavailable") {
      return true;
    }
  }
  const saved = get(savedLayoutAtom);
  const layout = get(layoutStateAtom);
  return (
    saved !== undefined &&
    (layout.selectedLayout !== saved.selectedLayout ||
      !isEqual(layout.layoutData, saved.layoutData))
  );
});
