/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { CellId } from "@/core/cells/ids";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import { INTERNAL_SQL_ENGINES } from "@/core/datasets/engines";
import { datasetTablesAtom } from "@/core/datasets/state";
import { store } from "@/core/state/jotai";
import { storageNamespacesAtom } from "@/core/storage/state";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import { Logger } from "@/utils/Logger";

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
 * Sets `name` to `kind`, logging (and overwriting) if the name was already
 * claimed by a different kind. This should be rare.
 */
function setEntity(
  entities: Map<string, CodeLensKind>,
  name: string,
  kind: CodeLensKind,
): void {
  const existing = entities.get(name);
  if (existing !== undefined && existing !== kind) {
    Logger.error(
      `[code-lens] "${name}" is claimed by both a ${existing} and a ${kind} entity; keeping ${kind}`,
    );
  }
  entities.set(name, kind);
}

/**
 * All datasource (dataframe/SQL engine) and storage bucket names in the
 * notebook, keyed by name, independent of any particular cell.
 */
const lensEntityKindsAtom = atom((get) => {
  const entities = new Map<string, CodeLensKind>();
  for (const table of get(datasetTablesAtom)) {
    if (table.variable_name) {
      setEntity(entities, table.variable_name, "table");
    }
  }
  for (const name of get(dataConnectionsMapAtom).keys()) {
    if (!INTERNAL_SQL_ENGINES.has(name)) {
      setEntity(entities, name, "connection");
    }
  }
  for (const namespace of get(storageNamespacesAtom)) {
    setEntity(entities, namespace.name, "bucket");
  }
  return entities;
});

interface LensEntitiesByCell {
  byCell: Map<CellId, Map<string, CodeLensKind>>;
  /**
   * Entities the kernel hasn't reported a variable for yet (still executing,
   * or just typed), so they can't be attributed to a declaring cell.
   */
  pending: Map<string, CodeLensKind>;
}

/**
 * Groups `lensEntityKindsAtom` by declaring cell, once per store update.
 * With C cells and T datasource/bucket entities, this turns
 * an O(C x T) per-round cost (every cell re-scanning every entity) into O(T) here.
 */
const lensEntitiesByCellAtom = atom((get): LensEntitiesByCell => {
  const kinds = get(lensEntityKindsAtom);
  const variables = get(variablesAtom);
  const byCell = new Map<CellId, Map<string, CodeLensKind>>();
  const pending = new Map<string, CodeLensKind>();

  for (const [name, kind] of kinds) {
    const variable = variables[name as VariableName];
    if (variable == null) {
      pending.set(name, kind);
      continue;
    }
    for (const declaringCell of variable.declaredBy) {
      let forCell = byCell.get(declaringCell);
      if (!forCell) {
        forCell = new Map();
        byCell.set(declaringCell, forCell);
      }
      forCell.set(name, kind);
    }
  }

  return { byCell, pending };
});

/**
 * Variables declared in `cellId` that are datasources (dataframes and SQL
 * engines) or storage buckets, keyed by variable name.
 */
export function getLensEntities(cellId: CellId): Map<string, CodeLensKind> {
  const { byCell, pending } = store.get(lensEntitiesByCellAtom);
  const entities = new Map(byCell.get(cellId));
  // Be permissive when the kernel hasn't reported a variable yet: any cell
  // could turn out to be the declaring one.
  for (const [name, kind] of pending) {
    if (!entities.has(name)) {
      entities.set(name, kind);
    }
  }
  return entities;
}
