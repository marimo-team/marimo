/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import type { DataTable, DataTableColumn } from "@/core/kernel/messages";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { DatasetColumnPreview } from "../column-preview";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={store}>{children}</Provider>
);

const table: DataTable = {
  name: "users",
  columns: [],
  source: "my_engine",
  // Not "connection"/"catalog", so a preview is requested on mount.
  source_type: "duckdb",
  type: "table",
  engine: "my_engine" as DataTable["engine"],
  indexes: null,
  num_columns: null,
  num_rows: null,
  variable_name: null,
  primary_keys: null,
};

const column = { name: "email" } as DataTableColumn;

function renderPreview(sqlTableContext?: SQLTableContext) {
  const client = MockRequestClient.create();
  store.set(requestClientAtom, client);
  render(
    <DatasetColumnPreview
      table={table}
      column={column}
      preview={undefined}
      onAddColumnChart={vi.fn()}
      sqlTableContext={sqlTableContext}
    />,
    { wrapper },
  );
  return client;
}

const ctx = (
  overrides: Partial<SQLTableContext> & { database: string; schema: string },
): SQLTableContext => ({
  engine: "my_engine",
  dialect: "duckdb",
  ...overrides,
});

describe("DatasetColumnPreview fullyQualifiedTableName", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses just the table name without a SQL context", () => {
    const client = renderPreview(undefined);
    expect(client.previewDatasetColumn).toHaveBeenCalledWith(
      expect.objectContaining({ fullyQualifiedTableName: "users" }),
    );
  });

  it("qualifies with database and schema for flat engines", () => {
    const client = renderPreview(ctx({ database: "db", schema: "public" }));
    expect(client.previewDatasetColumn).toHaveBeenCalledWith(
      expect.objectContaining({ fullyQualifiedTableName: "db.public.users" }),
    );
  });

  it("does not emit a double dot for schemaless tables", () => {
    // Regression: previously produced "db..users".
    const client = renderPreview(ctx({ database: "db", schema: "" }));
    expect(client.previewDatasetColumn).toHaveBeenCalledWith(
      expect.objectContaining({ fullyQualifiedTableName: "db.users" }),
    );
  });

  it("includes the full schema path for nested namespaces", () => {
    // Regression: previously dropped schemaPath and emitted "top.deep.users".
    const client = renderPreview(
      ctx({ database: "top", schema: "deep", schemaPath: ["nested", "deep"] }),
    );
    expect(client.previewDatasetColumn).toHaveBeenCalledWith(
      expect.objectContaining({
        fullyQualifiedTableName: "top.nested.deep.users",
      }),
    );
  });
});
