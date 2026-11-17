/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { Command, CommandList } from "@/components/ui/command";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  dataSourceConnectionsAtom,
  type SQLTableContext,
} from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom, exportedForTesting } from "@/core/datasets/state";
import type { DataTable } from "@/core/kernel/messages";
import { requestClientAtom } from "@/core/network/requests";
import {
  DataSources,
  hideEmptyDatasourcesAtom,
  TableList,
} from "../datasources";

beforeAll(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

const table: DataTable = {
  name: "reports",
  columns: [
    {
      name: "amount",
      type: "integer",
      external_type: "INTEGER",
      sample_values: [],
    },
  ],
  source: "memory",
  source_type: "duckdb",
  type: "table",
  engine: null,
  indexes: null,
  num_columns: 1,
  num_rows: null,
  variable_name: null,
  primary_keys: null,
};

describe("Datasource column preview responses", () => {
  it.each([
    { path: ["main"], qualifiedName: '"memory"."main"."reports"' },
    {
      path: ["finance", "reports"],
      qualifiedName: '"memory"."finance"."reports"."reports"',
    },
    {
      path: ["finance.reports"],
      qualifiedName: '"memory"."finance.reports"."reports"',
    },
    {
      path: ['fi"nance', "reports"],
      qualifiedName: '"memory"."fi""nance"."reports"."reports"',
    },
  ])(
    "renders the returned preview for $path",
    async ({ path, qualifiedName }) => {
      const store = createStore();
      const client = MockRequestClient.create();
      store.set(requestClientAtom, client);
      const context: SQLTableContext = {
        engine: DUCKDB_ENGINE,
        database: "memory",
        schema: path.at(-1) ?? "",
        schemaPath: path,
        dialect: "duckdb",
      };
      render(
        <Provider store={store}>
          <TooltipProvider>
            <Command shouldFilter={false}>
              <CommandList>
                <TableList tables={[table]} sqlTableContext={context} />
              </CommandList>
            </Command>
          </TooltipProvider>
        </Provider>,
      );

      fireEvent.click(await screen.findByText("reports"));
      fireEvent.click(await screen.findByText("amount"));
      await waitFor(() => {
        expect(client.previewDatasetColumn).toHaveBeenCalledWith(
          expect.objectContaining({ fullyQualifiedTableName: qualifiedName }),
        );
      });
      expect(screen.getByText("Loading...")).toBeInTheDocument();

      const actions = exportedForTesting.createActions((action) => {
        store.set(datasetsAtom, (state) =>
          exportedForTesting.reducer(state, action),
        );
      });
      act(() => {
        actions.addColumnPreview({
          table_name: qualifiedName,
          column_name: "amount",
          stats: { min: 42 },
          error: null,
          missing_packages: null,
          chart_spec: null,
          chart_code: null,
        });
      });

      expect(await screen.findByText("42")).toBeInTheDocument();
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    },
  );
});

it("activates a schema and a table with the same path independently using the keyboard", async () => {
  const store = createStore();
  store.set(requestClientAtom, MockRequestClient.create());
  store.set(hideEmptyDatasourcesAtom, false);
  store.set(dataSourceConnectionsAtom, {
    latestEngineSelected: DUCKDB_ENGINE,
    connectionsMap: new Map([
      [
        DUCKDB_ENGINE,
        {
          name: DUCKDB_ENGINE,
          dialect: "duckdb",
          source: "duckdb",
          display_name: "DuckDB (In-Memory)",
          databases: [
            {
              name: "memory",
              dialect: "duckdb",
              schemas: [
                {
                  name: "finance",
                  tables: [table],
                  child_schemas: [{ name: "reports", tables: [] }],
                },
              ],
            },
          ],
        },
      ],
    ]),
  });
  render(
    <Provider store={store}>
      <TooltipProvider>
        <DataSources />
      </TooltipProvider>
    </Provider>,
  );
  fireEvent.click(await screen.findByText("memory"));
  fireEvent.click(await screen.findByText("finance"));
  await waitFor(() => {
    expect(screen.getAllByText("reports")).toHaveLength(2);
  });

  const input = screen.getByRole("combobox");
  input.focus();
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(await screen.findByText("No tables found")).toBeInTheDocument();
  expect(screen.queryByText("amount")).not.toBeInTheDocument();

  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(await screen.findByText("amount")).toBeInTheDocument();
  expect(screen.getByText("No tables found")).toBeInTheDocument();
});
