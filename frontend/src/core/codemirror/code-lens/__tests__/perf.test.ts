/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Regression guards for code-lens hot paths: assert wall time stays within a
 * generous budget for a large, synthetic notebook.
 */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import { dataSourceConnectionsAtom } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom } from "@/core/datasets/state";
import type { QualifiedColumn } from "@/core/datasets/types";
import type { DataTable } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { storageAtom } from "@/core/storage/state";
import { variablesAtom } from "@/core/variables/state";
import type { Variables } from "@/core/variables/types";
import { findCacheSites, findDeclarationSites } from "../analyzer";
import { getLensEntities } from "../entities";

function pythonState(code: string): EditorState {
  return EditorState.create({ doc: code, extensions: [python()] });
}

describe("code-lens performance", () => {
  it("getLensEntities stays fast across many cells in a large notebook", () => {
    const DATASOURCE_COUNT = 2000;
    const CELL_COUNT = 1000;

    const tables: DataTable[] = [];
    const variables: Variables = {};
    for (let i = 0; i < DATASOURCE_COUNT; i++) {
      const name = variableName(`table_${i}`);
      tables.push({
        name,
        source: "memory",
        source_type: "local",
        num_rows: 1,
        num_columns: 1,
        columns: [],
        variable_name: name,
      });
      // Every datasource is owned by a distinct cell, like a real notebook.
      variables[name] = {
        name,
        declaredBy: [cellId(`owner-${i}`)],
        usedBy: [],
      };
    }
    store.set(datasetsAtom, {
      tables,
      expandedTables: new Set<string>(),
      expandedColumns: new Set<QualifiedColumn>(),
      columnsPreviews: new Map(),
    });
    store.set(storageAtom, {
      namespaces: [],
      entriesByPath: new Map(),
      pageMetadataByPath: new Map(),
    });
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map(),
    });
    store.set(variablesAtom, variables);

    const cellIds: CellId[] = Array.from({ length: CELL_COUNT }, (_, i) =>
      cellId(`cell-${i}`),
    );

    const start = performance.now();
    for (const id of cellIds) {
      getLensEntities(id);
    }
    const elapsed = performance.now() - start;

    // Rescanning all 2000 datasources per cell (instead of an O(1) lookup
    // into a precomputed per-cell index) would take on the order of seconds
    // here; 200ms leaves generous headroom for slow CI while still catching
    // that kind of regression.
    expect(elapsed).toBeLessThan(200);
  });

  it("findCacheSites stays fast for a large cell, valid or not", () => {
    const lines: string[] = [];
    for (let i = 0; i < 500; i++) {
      lines.push(`@mo.cache`, `def fn_${i}(x):`, `    return x + ${i}`, "");
    }
    const validCode = lines.join("\n");
    // Trailing unclosed paren makes the whole tree unparsable, mimicking a
    // cell mid-edit — this must bail out quickly rather than scanning anyway.
    const brokenCode = `${validCode}\ndf = (`;

    const start = performance.now();
    findCacheSites(pythonState(validCode));
    findCacheSites(pythonState(brokenCode));
    const elapsed = performance.now() - start;

    expect(elapsed).toBeLessThan(200);
  });

  it("findDeclarationSites stays fast for a large cell", () => {
    const lines: string[] = [];
    const names = new Set<string>();
    for (let i = 0; i < 2000; i++) {
      lines.push(`var_${i} = compute_${i}()`);
      names.add(`var_${i}`);
    }
    const state = pythonState(lines.join("\n"));

    const start = performance.now();
    findDeclarationSites({ state, names });
    const elapsed = performance.now() - start;

    expect(elapsed).toBeLessThan(200);
  });
});
