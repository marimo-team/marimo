/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import {
  type DataSourceConnection,
  dataSourceConnectionsAtom,
} from "@/core/datasets/data-source-connections";
import { type ConnectionName, DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom } from "@/core/datasets/state";
import type { QualifiedColumn } from "@/core/datasets/types";
import type { DataTable } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { storageAtom } from "@/core/storage/state";
import type { StorageNamespace } from "@/core/storage/types";
import { variablesAtom } from "@/core/variables/state";
import type { Variables } from "@/core/variables/types";
import { Logger } from "@/utils/Logger";
import { getLensEntities } from "../entities";

const CELL = cellId("cell1");
const OTHER_CELL = cellId("other-cell");

const table = (name: string): DataTable => ({
  name,
  source: "memory",
  source_type: "local",
  num_rows: 1,
  num_columns: 1,
  columns: [],
  variable_name: variableName(name),
});

const namespace = (name: string): StorageNamespace => ({
  name: variableName(name),
  displayName: name,
  protocol: "s3",
  rootPath: `s3://${name}`,
  backendType: "obstore",
  storageEntries: [],
});

const connection = (name: string): DataSourceConnection => ({
  name: name as ConnectionName,
  source: "postgres",
  dialect: "postgresql",
  display_name: name,
  databases: [],
});

function seedStore(opts: {
  tables?: DataTable[];
  namespaces?: StorageNamespace[];
  connections?: DataSourceConnection[];
  variables?: Variables;
}) {
  store.set(datasetsAtom, {
    tables: opts.tables ?? [],
    expandedTables: new Set<string>(),
    expandedColumns: new Set<QualifiedColumn>(),
    columnsPreviews: new Map(),
  });
  store.set(storageAtom, {
    namespaces: opts.namespaces ?? [],
    entriesByPath: new Map(),
    pageMetadataByPath: new Map(),
  });
  store.set(dataSourceConnectionsAtom, {
    latestEngineSelected: DUCKDB_ENGINE,
    connectionsMap: new Map((opts.connections ?? []).map((c) => [c.name, c])),
  });
  store.set(variablesAtom, opts.variables ?? {});
}

describe("getLensEntities", () => {
  beforeEach(() => {
    seedStore({});
    vi.restoreAllMocks();
  });

  it("returns an empty map when there are no entities", () => {
    expect(getLensEntities(CELL)).toEqual(new Map());
  });

  it("includes tables, connections, and buckets declared in the cell", () => {
    seedStore({
      tables: [table("df")],
      connections: [connection("engine")],
      namespaces: [namespace("bucket")],
    });

    const entities = getLensEntities(CELL);
    expect(entities).toEqual(
      new Map([
        ["df", "table"],
        ["engine", "connection"],
        ["bucket", "bucket"],
      ]),
    );
  });

  it("excludes the internal DuckDB engine from connections", () => {
    seedStore({ connections: [connection(DUCKDB_ENGINE)] });
    expect(getLensEntities(CELL)).toEqual(new Map());
  });

  it("excludes entities declared by a different cell", () => {
    seedStore({
      tables: [table("df")],
      variables: {
        [variableName("df")]: {
          name: variableName("df"),
          declaredBy: [OTHER_CELL],
          usedBy: [],
        },
      },
    });

    expect(getLensEntities(CELL)).toEqual(new Map());
  });

  it("is permissive when the kernel hasn't reported the variable yet", () => {
    // No entry in `variablesAtom` for "df" at all.
    seedStore({ tables: [table("df")] });
    expect(getLensEntities(CELL)).toEqual(new Map([["df", "table"]]));
  });

  it("last-write-wins and logs an error when a name is claimed by more than one kind", () => {
    const errorSpy = vi
      .spyOn(Logger, "error")
      .mockImplementation(() => undefined);
    seedStore({
      tables: [table("shared")],
      connections: [connection("shared")],
    });

    const entities = getLensEntities(CELL);

    expect(entities.get("shared")).toBe("connection");
    expect(errorSpy).toHaveBeenCalledExactlyOnceWith(
      expect.stringContaining("shared"),
    );
  });

  it("does not log when the same name repeats with the same kind", () => {
    const errorSpy = vi
      .spyOn(Logger, "error")
      .mockImplementation(() => undefined);
    seedStore({ tables: [table("df"), table("df")] });

    const entities = getLensEntities(CELL);

    expect(entities.get("df")).toBe("table");
    expect(errorSpy).not.toHaveBeenCalled();
  });
});
