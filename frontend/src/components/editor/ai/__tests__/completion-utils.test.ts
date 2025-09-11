/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { dataSourceConnectionsAtom } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom } from "@/core/datasets/state";
import type { DatasetsState } from "@/core/datasets/types";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { Variable, VariableName } from "@/core/variables/types";
import { getAICompletionBody, splitCodeIntoCells } from "../completion-utils";

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

    const input = "Use @data://dataset1 and @data://dataset2 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="dataset1" source="unknown">
      Columns:
        - col1: number
        - col2: string</data>

      <data name="dataset2" source="unknown">
      Columns:
        - col3: boolean
        - col4: date</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should handle input with no mentioned datasets", () => {
    const input = "Perform some analysis without mentioning @data://datasets";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input =
      "Use @data://existingDataset and @data://nonExistentDataset for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="existingDataset" source="unknown">
      Columns:
        - col1: number
        - col2: string</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input =
      "Use @data://dataset.with.dots and @data://regular_dataset for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="dataset.with.dots" source="unknown">
      Columns:
        - col1: number
        - col2: string</data>

      <data name="regular_dataset" source="unknown">
      Columns:
        - col3: boolean</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input = "Use @data://table1 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="table1" source="unknown">
      Columns:
        - col1: number</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input = "Use @variable://var1 and @variable://var2 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<variable name="var1" dataType="string">"string value"</variable>

      <variable name="var2" dataType="number">"42"</variable>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input = "Use @data://dataset1 and @variable://var1 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="dataset1" source="unknown">
      Columns:
        - col1: number
        - col2: string</data>

      <variable name="var1" dataType="string">"string value"</variable>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input =
      "Use @variable://existingVar and @variable://nonExistentVar for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<variable name="existingVar" dataType="string">"string value"</variable>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input = "Use @data://conflict for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="conflict" source="unknown">
      Columns:
        - col1: number</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });
});

describe("splitCodeIntoCells", () => {
  it("should split code into cells", () => {
    const code = "```python\nprint('Hello, world!')\n```";
    const result = splitCodeIntoCells(code);
    expect(result).toEqual([
      { language: "python", code: "print('Hello, world!')" },
    ]);
  });

  it("should split code into multiple cells", () => {
    const code =
      "```python\nprint('Hello, world!')\n```\n```sql\nSELECT * FROM users\n```\n```markdown\n# Hello, world!\n```";
    const result = splitCodeIntoCells(code);
    expect(result).toEqual([
      { language: "python", code: "print('Hello, world!')" },
      { language: "sql", code: "SELECT * FROM users" },
      { language: "markdown", code: "# Hello, world!" },
    ]);
  });

  it("should handle cells with similar language identifiers", () => {
    const code =
      "```python\nprint('Hello, world!')\n```\n```python\nprint('Hello, world!')\n```";
    const result = splitCodeIntoCells(code);
    expect(result).toEqual([
      { language: "python", code: "print('Hello, world!')" },
      { language: "python", code: "print('Hello, world!')" },
    ]);
  });

  it("should handle code with no backticks", () => {
    // Assume code is in 1 cell and python
    const code = "print('Hello, world!')";
    const result = splitCodeIntoCells(code);
    expect(result).toEqual([
      { language: "python", code: "print('Hello, world!')" },
    ]);
  });

  it("should handle empty cells", () => {
    const code = "```python\n\n```";
    const result = splitCodeIntoCells(code);
    expect(result).toEqual([{ language: "python", code: "```python\n\n```" }]);
  });

  it("should handle code with no language identifier", () => {
    // Defaults to python
    const code = "```\nprint('Hello, world!')\n```";
    const result = splitCodeIntoCells(code);
    expect(result).toEqual([
      { language: "python", code: "print('Hello, world!')" },
    ]);
  });
});
