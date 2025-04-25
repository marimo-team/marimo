/* Copyright 2024 Marimo. All rights reserved. */
import { describe, beforeEach, it, expect, vi, type Mock } from "vitest";
import { getAICompletionBody } from "../completion-utils";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { datasetsAtom } from "@/core/datasets/state";
import { store } from "@/core/state/jotai";
import type { DatasetsState } from "@/core/datasets/types";
import {
  dataSourceConnectionsAtom,
  DUCKDB_ENGINE,
} from "@/core/datasets/data-source-connections";
import { variablesAtom } from "@/core/variables/state";
import type { Variable, VariableName } from "@/core/variables/types";

// Mock getCodes function
vi.mock("@/core/codemirror/copilot/getCodes", () => ({
  getCodes: vi.fn(),
}));

describe("getAICompletionBody", () => {
  beforeEach(() => {
    // Reset the Jotai store before each test
    store.set(datasetsAtom, {
      tables: [],
    } as unknown as DatasetsState);
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map(),
    });
    store.set(variablesAtom, {});
    (getCodes as Mock).mockReturnValue("// Some other code");
  });

  it("should return the correct completion body with mentioned datasets", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "dataset1",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
      {
        name: "dataset2",
        columns: [
          { name: "col3", type: "boolean" },
          { name: "col4", type: "date" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const input = "Use @dataset1 and @dataset2 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "dataset1",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
          {
            name: "dataset2",
            columns: [
              { name: "col3", type: "boolean" },
              { name: "col4", type: "date" },
            ],
          },
        ],
        variables: [],
      },
    });
  });

  it("should handle input with no mentioned datasets", () => {
    const input = "Perform some analysis without mentioning datasets";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [],
        variables: [],
      },
    });
  });

  it("should handle input with non-existent datasets", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "existingDataset",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const input = "Use @existingDataset and @nonExistentDataset for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "existingDataset",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
        ],
        variables: [],
      },
    });
  });

  it("should handle dataset names with dots", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "dataset.with.dots",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
      {
        name: "regular_dataset",
        columns: [{ name: "col3", type: "boolean" }],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const input = "Use @dataset.with.dots and @regular_dataset for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "dataset.with.dots",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
          {
            name: "regular_dataset",
            columns: [{ name: "col3", type: "boolean" }],
          },
        ],
        variables: [],
      },
    });
  });

  it("should handle connections", () => {
    // Set up test data in the Jotai store
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_schema: "default_schema",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "default_schema",
              tables: [
                { name: "table1", columns: [{ name: "col1", type: "number" }] },
                { name: "table2", columns: [] },
              ],
            },
            {
              name: "other_schema",
              tables: [{ name: "table3", columns: [] }],
            },
          ],
        },
      ],
    };
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const input = "Use @table1 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "table1",
            columns: [{ name: "col1", type: "number" }],
          },
        ],
        variables: [],
      },
    });
  });

  it("should return the correct completion body with mentioned variables", () => {
    // Set up test data in the Jotai store
    const testVariables: Record<VariableName, Variable> = {
      ["var1" as VariableName]: {
        name: "var1" as VariableName,
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
      ["var2" as VariableName]: {
        name: "var2" as VariableName,
        value: "42",
        dataType: "number",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @var1 and @var2 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [],
        variables: [
          {
            name: "var1",
            valueType: "string",
            previewValue: "string value",
          },
          {
            name: "var2",
            valueType: "number",
            previewValue: "42",
          },
        ],
      },
    });
  });

  it("should handle input with both datasets and variables", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "dataset1",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const testVariables: Record<VariableName, Variable> = {
      ["var1" as VariableName]: {
        name: "var1" as VariableName,
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @dataset1 and @var1 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "dataset1",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
        ],
        variables: [
          {
            name: "var1",
            valueType: "string",
            previewValue: "string value",
          },
        ],
      },
    });
  });

  it("should handle non-existent variables", () => {
    // Set up test data in the Jotai store
    const testVariables: Record<VariableName, Variable> = {
      ["existingVar" as VariableName]: {
        name: "existingVar" as VariableName,
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @existingVar and @nonExistentVar for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [],
        variables: [
          {
            name: "existingVar",
            valueType: "string",
            previewValue: "string value",
          },
        ],
      },
    });
  });

  it("should prioritize datasets over variables when there's a name conflict", () => {
    // Set up test data in the Jotai store with a name conflict
    const testDatasets = [
      {
        name: "conflict",
        columns: [{ name: "col1", type: "number" }],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const testVariables: Record<VariableName, Variable> = {
      ["conflict" as VariableName]: {
        name: "conflict" as VariableName,
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @conflict for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "conflict",
            columns: [{ name: "col1", type: "number" }],
          },
        ],
        variables: [],
      },
    });
  });
});
