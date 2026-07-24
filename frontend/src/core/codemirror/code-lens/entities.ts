/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import { INTERNAL_SQL_ENGINES } from "@/core/datasets/engines";
import { datasetTablesAtom } from "@/core/datasets/state";
import { store } from "@/core/state/jotai";
import { storageNamespacesAtom } from "@/core/storage/state";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";

export type CodeLensKind = "table" | "connection" | "bucket" | "cache";

export interface CodeLensSpec {
  /** Document position the icon is anchored at */
  pos: number;
  kind: CodeLensKind;
  /** Variable name for entities; a stable identity key for cache sites */
  name: string;
  /** Extra context for cache sites */
  cache?: {
    boundName: string | null;
    cacheName: string | null;
  };
}

/**
 * Variables declared in `cellId` that are datasources (dataframes and SQL
 * engines) or storage buckets, keyed by variable name.
 */
export function getLensEntities(cellId: CellId): Map<string, CodeLensKind> {
  const entities = new Map<string, CodeLensKind>();
  const variables = store.get(variablesAtom);

  // Only decorate the declaring cell. Be permissive when the kernel hasn't
  // reported the variable (yet).
  const isDeclaredHere = (name: string) => {
    const variable = variables[name as VariableName];
    return variable == null || variable.declaredBy.includes(cellId);
  };

  for (const table of store.get(datasetTablesAtom)) {
    if (table.variable_name && isDeclaredHere(table.variable_name)) {
      entities.set(table.variable_name, "table");
    }
  }
  for (const name of store.get(dataConnectionsMapAtom).keys()) {
    if (!INTERNAL_SQL_ENGINES.has(name) && isDeclaredHere(name)) {
      entities.set(name, "connection");
    }
  }
  for (const namespace of store.get(storageNamespacesAtom)) {
    if (isDeclaredHere(namespace.name)) {
      entities.set(namespace.name, "bucket");
    }
  }
  return entities;
}
