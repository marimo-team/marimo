/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { describe, expect, it, vi } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { Variable, VariableName, Variables } from "@/core/variables/types";
import { type VariableContextItem, VariableContextProvider } from "../variable";

// Mock the variable completions module
vi.mock("@/core/codemirror/completion/variable-completions", () => ({
  getVariableCompletions: vi.fn(
    (
      variables: Variables,
      _tableNames: string[],
      boost: number,
      prefix: string,
    ) => {
      return Object.entries(variables).map(([name, variable]) => ({
        name: `${prefix}${name}`,
        displayname: name,
        detail: variable.dataType || "unknown",
        boost,
        type: variable.dataType || "variable",
        apply: `${prefix}${name}`,
        section: "Variables",
      }));
    },
  ),
}));

// Mock data for testing
const createMockVariable = (
  name: string,
  options: Partial<Variable> = {},
): Variable => ({
  name: name as VariableName,
  declaredBy: ["cell1" as CellId],
  usedBy: ["cell2" as CellId],
  value: `value_of_${name}`,
  dataType: "str",
  ...options,
});

describe("VariableContextProvider", () => {
  describe("getItems", () => {
    it("should return empty array when no variables", () => {
      const variables: Variables = {};
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("empty-variables");
    });

    it("should return variable items for single variable", () => {
      const variables: Variables = {
        ["user_name" as VariableName]: createMockVariable("user_name", {
          value: '"John Doe"',
          dataType: "str",
        }),
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("single-variable");
    });

    it("should return variable items for multiple variables with different types", () => {
      const variables: Variables = {
        ["user_id" as VariableName]: createMockVariable("user_id", {
          value: "123",
          dataType: "int",
          declaredBy: ["cell1" as CellId],
          usedBy: ["cell2" as CellId, "cell3" as CellId],
        }),
        ["is_active" as VariableName]: createMockVariable("is_active", {
          value: "True",
          dataType: "bool",
          declaredBy: ["cell2" as CellId],
          usedBy: [],
        }),
        ["scores" as VariableName]: createMockVariable("scores", {
          value: "[1, 2, 3, 4, 5]",
          dataType: "list",
          declaredBy: ["cell3" as CellId],
          usedBy: ["cell4" as CellId],
        }),
        ["config" as VariableName]: createMockVariable("config", {
          value: '{"debug": true, "timeout": 30}',
          dataType: "dict",
          declaredBy: ["cell1" as CellId],
          usedBy: ["cell2" as CellId, "cell4" as CellId],
        }),
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("multiple-variables");
    });

    it("should handle variables with null/undefined values", () => {
      const variables: Variables = {
        ["null_var" as VariableName]: createMockVariable("null_var", {
          value: null,
          dataType: "NoneType",
        }),
        ["undefined_var" as VariableName]: createMockVariable("undefined_var", {
          value: undefined,
          dataType: null,
        }),
        ["empty_string" as VariableName]: createMockVariable("empty_string", {
          value: '""',
          dataType: "str",
        }),
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("null-undefined-variables");
    });

    it("should handle complex data types", () => {
      const variables: Variables = {
        ["df" as VariableName]: createMockVariable("df", {
          value: "<DataFrame shape: (100, 5)>",
          dataType: "pandas.DataFrame",
          declaredBy: ["cell1" as CellId],
          usedBy: ["cell2" as CellId, "cell3" as CellId],
        }),
        ["model" as VariableName]: createMockVariable("model", {
          value: "<sklearn.linear_model.LinearRegression>",
          dataType: "sklearn.linear_model._base.LinearRegression",
          declaredBy: ["cell4" as CellId],
          usedBy: ["cell5" as CellId],
        }),
        ["array" as VariableName]: createMockVariable("array", {
          value: "array([1, 2, 3, 4, 5])",
          dataType: "numpy.ndarray",
          declaredBy: ["cell2" as CellId],
          usedBy: ["cell3" as CellId],
        }),
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("complex-data-types");
    });

    it("should handle variables with special characters in names", () => {
      const variables: Variables = {
        ["_private_var" as VariableName]: createMockVariable("_private_var", {
          value: "42",
          dataType: "int",
        }),
        ["var_with_numbers123" as VariableName]: createMockVariable(
          "var_with_numbers123",
          {
            value: '"test"',
            dataType: "str",
          },
        ),
        ["CONSTANT_VAR" as VariableName]: createMockVariable("CONSTANT_VAR", {
          value: "3.14159",
          dataType: "float",
        }),
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("special-chars-variables");
    });
  });

  describe("formatContext", () => {
    it("should format context for basic variable", () => {
      const variable = createMockVariable("username", {
        value: '"alice"',
        dataType: "str",
      });
      const item: VariableContextItem = {
        type: "variable",
        uri: "username",
        name: "username",
        description: "str",
        data: { variable },
      };

      const variables: Variables = { ["username" as VariableName]: variable };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("basic-variable-context");
    });

    it("should format context for variable without dataType", () => {
      const variable = createMockVariable("mystery_var", {
        value: "some_value",
        dataType: null,
      });
      const item: VariableContextItem = {
        type: "variable",
        uri: "mystery_var",
        name: "mystery_var",
        description: "",
        data: { variable },
      };

      const variables: Variables = {
        ["mystery_var" as VariableName]: variable,
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("no-datatype-variable-context");
    });

    it("should format context for variable with complex value", () => {
      const variable = createMockVariable("complex_data", {
        value:
          '{"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}], "total": 2}',
        dataType: "dict",
      });
      const item: VariableContextItem = {
        type: "variable",
        uri: "complex_data",
        name: "complex_data",
        description: "dict",
        data: { variable },
      };

      const variables: Variables = {
        ["complex_data" as VariableName]: variable,
      };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("complex-value-variable-context");
    });

    it("should format context for dataframe variable", () => {
      const variable = createMockVariable("sales_df", {
        value:
          "<DataFrame shape: (1000, 8)>\n   date    product  quantity  price\n0  2023-01-01  Widget A    10    29.99\n1  2023-01-02  Widget B     5    49.99\n...",
        dataType: "pandas.DataFrame",
      });
      const item: VariableContextItem = {
        type: "variable",
        uri: "sales_df",
        name: "sales_df",
        description: "pandas.DataFrame",
        data: { variable },
      };

      const variables: Variables = { ["sales_df" as VariableName]: variable };
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("dataframe-variable-context");
    });
  });

  describe("provider properties", () => {
    it("should have correct provider properties", () => {
      const variables: Variables = {};
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new VariableContextProvider(variables, tablesMap);

      expect(provider.title).toBe("Variables");
      expect(provider.mentionPrefix).toBe("@");
      expect(provider.contextType).toBe("variable");
    });
  });

  describe("integration with tables", () => {
    it("should work with both variables and tables", () => {
      const variables: Variables = {
        ["df" as VariableName]: createMockVariable("df", {
          dataType: "pandas.DataFrame",
          value: "<DataFrame shape: (50, 3)>",
        }),
        ["connection_string" as VariableName]: createMockVariable(
          "connection_string",
          {
            dataType: "str",
            value: '"postgresql://localhost:5432/mydb"',
          },
        ),
      };

      const tablesMap: DatasetTablesMap = new Map([
        ["users", {} as any],
        ["products", {} as any],
      ]);

      const provider = new VariableContextProvider(variables, tablesMap);

      const items = provider.getItems();

      expect(items).toMatchSnapshot("variables-with-tables-items");
    });
  });
});
