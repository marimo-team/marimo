/* Copyright 2026 Marimo. All rights reserved. */

import type { CellAnalysis } from "@marimo-team/client/protocol";
import { atom, useAtomValue } from "jotai";
import type { CellId } from "../cells/ids";
import {
  activeNotebookReplicaAtom,
  confirmedDocumentAtom,
  notebookAnalysisAtom,
} from "../session/active-notebook";
import { Objects } from "@/utils/objects";
import type { VariableName, Variables } from "./types";

/** Null until the host has analyzed a revision of this notebook. */
const declaredVariablesAtom = atom((get): Variables | null => {
  const analysis = get(notebookAnalysisAtom);
  if (analysis === null) {
    return null;
  }

  const declarations: Variables = Object.create(null);
  const cells = Objects.entries<CellId, CellAnalysis>(analysis.cells);
  for (const [cellId, cell] of cells) {
    for (const name of cell.defs as VariableName[]) {
      const variable = (declarations[name] ??= {
        name,
        declaredBy: [],
        usedBy: [],
      });
      variable.declaredBy.push(cellId);
    }
  }
  for (const [cellId, cell] of cells) {
    for (const name of cell.refs as VariableName[]) {
      declarations[name]?.usedBy.push(cellId);
    }
  }
  return declarations;
});

export const variableBindingsAtom = atom((get) => {
  const replica = get(activeNotebookReplicaAtom);
  return replica && get(replica.shownDocumentAtom)
    ? get(replica.executionsAtom).variables
    : null;
});

const analysisMatchesDocumentAtom = atom((get) => {
  const document = get(confirmedDocumentAtom);
  return (
    document !== null &&
    get(notebookAnalysisAtom)?.document_etag === document.revision.etag
  );
});

const EMPTY: Variables = Object.freeze(Object.create(null));

export const variablesAtom = atom((get): Variables => {
  const declarations = get(declaredVariablesAtom);
  const bindings = get(variableBindingsAtom);
  if (!bindings?.size) {
    return declarations ?? EMPTY;
  }
  const current = get(analysisMatchesDocumentAtom);
  const variables: Variables = Object.assign(Object.create(null), declarations);
  for (const [cellId, items] of bindings) {
    for (const item of items.values()) {
      const name = item.name as VariableName;
      const declaration = declarations?.[name];
      const owner = declaration?.declaredBy.includes(cellId)
        ? declaration
        : undefined;
      if (current && declaration && !owner) {
        continue;
      }
      variables[name] = {
        ...(owner ?? { name, declaredBy: current ? [] : [cellId], usedBy: [] }),
        dataType: item.type,
        value: item.preview,
      };
    }
  }
  return variables;
});

export const useVariables = () => useAtomValue(variablesAtom);
