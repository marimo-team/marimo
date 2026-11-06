/* Copyright 2026 Marimo. All rights reserved. */

/** What the host lets this client do to the notebook. */

import { atom } from "jotai";
import { kioskModeAtom } from "../mode";
import { activeNotebookReplicaAtom } from "../session/active-notebook";

const NO_OPERATIONS: readonly string[] = [];

/** Operations the host advertises for this notebook, none until its stream is ready. */
export const notebookOperationsAtom = atom((get) => {
  const replica = get(activeNotebookReplicaAtom);
  const notebook = replica === null ? null : get(replica.notebookAtom);
  return notebook?.operations ?? NO_OPERATIONS;
});

/**
 * Whether this client may edit the document.
 *
 * TODO(MO-8028): The host advertises the same operations to every
 * connection of a notebook, so a kiosk connection, an interactor that may
 * not edit, narrows it here. Once the host narrows `operations` per
 * connection by consumer capability, the kiosk term goes.
 */
export const canEditAtom = atom(
  (get) =>
    !get(kioskModeAtom) &&
    get(notebookOperationsAtom).includes("notebook.edit"),
);
