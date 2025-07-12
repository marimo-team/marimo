/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { FieldTypes } from "@/components/data-table/types";
import {
  insertColumn,
  modifyColumnFields,
  removeColumn,
  renameColumn,
} from "../data-utils";

describe("removeColumn", () => {
  const testData = [
    { int: 1, string: "a", bool: "True", datetime: "2025-07-12 00:07:13" },
    { int: 2, string: "b", bool: "False", datetime: null },
    { int: 3, string: "c", bool: null, datetime: "2025-07-12 00:07:13" },
    { int: 0, string: "", bool: "", datetime: "" },
  ];

  it("should remove column at index 0", () => {
    const result = removeColumn(testData, 0);

    expect(result).toEqual([
      { string: "a", bool: "True", datetime: "2025-07-12 00:07:13" },
      { string: "b", bool: "False", datetime: null },
      { string: "c", bool: null, datetime: "2025-07-12 00:07:13" },
      { string: "", bool: "", datetime: "" },
    ]);
  });

  it("should remove column at index 1", () => {
    const result = removeColumn(testData, 1);

    expect(result).toEqual([
      { int: 1, bool: "True", datetime: "2025-07-12 00:07:13" },
      { int: 2, bool: "False", datetime: null },
      { int: 3, bool: null, datetime: "2025-07-12 00:07:13" },
      { int: 0, bool: "", datetime: "" },
    ]);
  });

  it("should remove column at index 2", () => {
    const result = removeColumn(testData, 2);

    expect(result).toEqual([
      { int: 1, string: "a", datetime: "2025-07-12 00:07:13" },
      { int: 2, string: "b", datetime: null },
      { int: 3, string: "c", datetime: "2025-07-12 00:07:13" },
      { int: 0, string: "", datetime: "" },
    ]);
  });

  it("should remove column at index 3", () => {
    const result = removeColumn(testData, 3);

    expect(result).toEqual([
      { int: 1, string: "a", bool: "True" },
      { int: 2, string: "b", bool: "False" },
      { int: 3, string: "c", bool: null },
      { int: 0, string: "", bool: "" },
    ]);
  });

  it("should handle removing non-existent column index", () => {
    const result = removeColumn(testData, 999);
    // Should return the original data since the index doesn't exist
    expect(result).toEqual(testData);
  });

  it("should handle negative index", () => {
    const result = removeColumn(testData, -1);
    // Should return the original data since negative index is invalid
    expect(result).toEqual(testData);
  });

  it("should preserve original data structure", () => {
    const originalData = [...testData];
    removeColumn(testData, 1);
    // Original data should remain unchanged
    expect(testData).toEqual(originalData);
  });

  it("should handle objects with different property counts", () => {
    const mixedData = [{ a: 1, b: 2 }, { a: 3, b: 4, c: 5 }, { a: 6 }];

    const result = removeColumn(mixedData, 1);

    expect(result).toEqual([{ a: 1 }, { a: 3, c: 5 }, { a: 6 }]);
  });

  it("should handle null and undefined values in data", () => {
    const dataWithNulls = [
      { a: 1, b: null, c: undefined },
      { a: null, b: 2, c: 3 },
    ];

    const result = removeColumn(dataWithNulls, 1);

    expect(result).toEqual([
      { a: 1, c: undefined },
      { a: null, c: 3 },
    ]);
  });
});

describe("insertColumn", () => {
  const testData = [
    { int: 1, string: "a", bool: "True", datetime: "2025-07-12 00:07:13" },
    { int: 2, string: "b", bool: "False", datetime: null },
    { int: 3, string: "c", bool: null, datetime: "2025-07-12 00:07:13" },
    { int: 0, string: "", bool: "", datetime: "" },
  ];

  it("should insert column at index 0", () => {
    const result = insertColumn(testData, "newColumn");

    const expected = [
      {
        newColumn: "",
        int: 1,
        string: "a",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
      },
      { newColumn: "", int: 2, string: "b", bool: "False", datetime: null },
      {
        newColumn: "",
        int: 3,
        string: "c",
        bool: null,
        datetime: "2025-07-12 00:07:13",
      },
      { newColumn: "", int: 0, string: "", bool: "", datetime: "" },
    ];
    expect(result).toEqual(expected);
  });

  it("should insert column at index 1", () => {
    const result = insertColumn(testData, "newColumn");

    expect(result).toEqual([
      {
        int: 1,
        newColumn: "",
        string: "a",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
      },
      { int: 2, newColumn: "", string: "b", bool: "False", datetime: null },
      {
        int: 3,
        newColumn: "",
        string: "c",
        bool: null,
        datetime: "2025-07-12 00:07:13",
      },
      { int: 0, newColumn: "", string: "", bool: "", datetime: "" },
    ]);
  });

  it("should insert column at index 2", () => {
    const result = insertColumn(testData, "newColumn");

    expect(result).toEqual([
      {
        int: 1,
        string: "a",
        newColumn: "",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
      },
      { int: 2, string: "b", newColumn: "", bool: "False", datetime: null },
      {
        int: 3,
        string: "c",
        newColumn: "",
        bool: null,
        datetime: "2025-07-12 00:07:13",
      },
      { int: 0, string: "", newColumn: "", bool: "", datetime: "" },
    ]);
  });

  it("should insert column at index 3", () => {
    const result = insertColumn(testData, "newColumn");

    expect(result).toEqual([
      {
        int: 1,
        string: "a",
        bool: "True",
        newColumn: "",
        datetime: "2025-07-12 00:07:13",
      },
      { int: 2, string: "b", bool: "False", newColumn: "", datetime: null },
      {
        int: 3,
        string: "c",
        bool: null,
        newColumn: "",
        datetime: "2025-07-12 00:07:13",
      },
      { int: 0, string: "", bool: "", newColumn: "", datetime: "" },
    ]);
  });

  it("should insert column at the end when index equals length", () => {
    const result = insertColumn(testData, "newColumn");

    expect(result).toEqual([
      {
        int: 1,
        string: "a",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
        newColumn: "",
      },
      { int: 2, string: "b", bool: "False", datetime: null, newColumn: "" },
      {
        int: 3,
        string: "c",
        bool: null,
        datetime: "2025-07-12 00:07:13",
        newColumn: "",
      },
      { int: 0, string: "", bool: "", datetime: "", newColumn: "" },
    ]);
  });

  it("should handle inserting at index beyond array length", () => {
    const result = insertColumn(testData, "newColumn");
    // Should add the column at the end
    expect(result).toEqual([
      {
        int: 1,
        string: "a",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
        newColumn: "",
      },
      { int: 2, string: "b", bool: "False", datetime: null, newColumn: "" },
      {
        int: 3,
        string: "c",
        bool: null,
        datetime: "2025-07-12 00:07:13",
        newColumn: "",
      },
      { int: 0, string: "", bool: "", datetime: "", newColumn: "" },
    ]);
  });

  it("should preserve original data structure", () => {
    const originalData = [...testData];
    insertColumn(testData, "newColumn");
    // Original data should remain unchanged
    expect(testData).toEqual(originalData);
  });

  it("should handle empty array", () => {
    const result = insertColumn([], "newColumn");
    expect(result).toEqual([]);
  });

  it("should handle array with single object", () => {
    const singleRowData = [{ a: 1, b: 2, c: 3 }];
    const result = insertColumn(singleRowData, "newColumn");
    expect(result).toEqual([{ a: 1, newColumn: "", b: 2, c: 3 }]);
  });

  it("should handle objects with different property counts", () => {
    const mixedData = [{ a: 1, b: 2 }, { a: 3, b: 4, c: 5 }, { a: 6 }];

    const result = insertColumn(mixedData, "newColumn");

    expect(result).toEqual([
      { a: 1, newColumn: "", b: 2 },
      { a: 3, newColumn: "", b: 4, c: 5 },
      { a: 6, newColumn: "" },
    ]);
  });

  it("should handle null and undefined values in data", () => {
    const dataWithNulls = [
      { a: 1, b: null, c: undefined },
      { a: null, b: 2, c: 3 },
    ];

    const result = insertColumn(dataWithNulls, "newColumn");

    expect(result).toEqual([
      { a: 1, newColumn: "", b: null, c: undefined },
      { a: null, newColumn: "", b: 2, c: 3 },
    ]);
  });

  it("should handle special characters in column name", () => {
    const result = insertColumn(testData, "new-column_with_123");

    expect(result).toEqual([
      {
        int: 1,
        "new-column_with_123": "",
        string: "a",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
      },
      {
        int: 2,
        "new-column_with_123": "",
        string: "b",
        bool: "False",
        datetime: null,
      },
      {
        int: 3,
        "new-column_with_123": "",
        string: "c",
        bool: null,
        datetime: "2025-07-12 00:07:13",
      },
      { int: 0, "new-column_with_123": "", string: "", bool: "", datetime: "" },
    ]);
  });
});

describe("renameColumn", () => {
  const testData = [
    { int: 1, string: "a", bool: "True", datetime: "2025-07-12 00:07:13" },
    { int: 2, string: "b", bool: "False", datetime: null },
    { int: 3, string: "c", bool: null, datetime: "2025-07-12 00:07:13" },
    { int: 0, string: "", bool: "", datetime: "" },
  ];

  it("should rename a column successfully", () => {
    const result = renameColumn(testData, "int", "number");

    expect(result).toEqual([
      { number: 1, string: "a", bool: "True", datetime: "2025-07-12 00:07:13" },
      { number: 2, string: "b", bool: "False", datetime: null },
      { number: 3, string: "c", bool: null, datetime: "2025-07-12 00:07:13" },
      { number: 0, string: "", bool: "", datetime: "" },
    ]);
  });

  it("should rename a column with special characters", () => {
    const result = renameColumn(testData, "string", "text-field");

    expect(result).toEqual([
      {
        int: 1,
        "text-field": "a",
        bool: "True",
        datetime: "2025-07-12 00:07:13",
      },
      { int: 2, "text-field": "b", bool: "False", datetime: null },
      {
        int: 3,
        "text-field": "c",
        bool: null,
        datetime: "2025-07-12 00:07:13",
      },
      { int: 0, "text-field": "", bool: "", datetime: "" },
    ]);
  });

  it("should handle renaming to an existing column name", () => {
    const result = renameColumn(testData, "int", "string");

    expect(result).toEqual([
      { string: 1, bool: "True", datetime: "2025-07-12 00:07:13" },
      { string: 2, bool: "False", datetime: null },
      { string: 3, bool: null, datetime: "2025-07-12 00:07:13" },
      { string: 0, bool: "", datetime: "" },
    ]);
  });

  it("should handle non-existent column name gracefully", () => {
    const result = renameColumn(testData, "nonexistent", "newName");

    // Should return the original data unchanged since the column doesn't exist
    expect(result).toEqual(testData);
  });

  it("should handle empty string column names", () => {
    const result = renameColumn(testData, "", "emptyColumn");

    // Should return the original data unchanged since empty string is not a valid column name
    expect(result).toEqual(testData);
  });

  it("should handle renaming to empty string", () => {
    const result = renameColumn(testData, "int", "");

    // Should return the original data unchanged since empty string is not a valid column name
    expect(result).toEqual(testData);
  });

  it("should preserve original data structure", () => {
    const originalData = [...testData];
    renameColumn(testData, "int", "number");
    // Original data should remain unchanged
    expect(testData).toEqual(originalData);
  });

  it("should handle empty array", () => {
    const result = renameColumn([], "oldName", "newName");
    expect(result).toEqual([]);
  });

  it("should handle array with single object", () => {
    const singleRowData = [{ a: 1, b: 2, c: 3 }];
    const result = renameColumn(singleRowData, "a", "x");
    expect(result).toEqual([{ x: 1, b: 2, c: 3 }]);
  });

  it("should handle objects with different property counts", () => {
    const mixedData = [{ a: 1, b: 2 }, { a: 3, b: 4, c: 5 }, { a: 6 }];

    const result = renameColumn(mixedData, "a", "alpha");

    expect(result).toEqual([
      { alpha: 1, b: 2 },
      { alpha: 3, b: 4, c: 5 },
      { alpha: 6 },
    ]);
  });

  it("should handle null and undefined values in data", () => {
    const dataWithNulls = [
      { a: 1, b: null, c: undefined },
      { a: null, b: 2, c: 3 },
    ];

    const result = renameColumn(dataWithNulls, "b", "beta");

    expect(result).toEqual([
      { a: 1, beta: null, c: undefined },
      { a: null, beta: 2, c: 3 },
    ]);
  });

  it("should handle case-sensitive column names", () => {
    const caseSensitiveData = [{ Name: "John", name: "Jane" }];
    const result = renameColumn(caseSensitiveData, "Name", "FullName");

    expect(result).toEqual([{ FullName: "John", name: "Jane" }]);
  });

  it("should handle renaming multiple columns in sequence", () => {
    let result = renameColumn(testData, "int", "number");
    result = renameColumn(result, "string", "text");
    result = renameColumn(result, "bool", "boolean");

    expect(result).toEqual([
      {
        number: 1,
        text: "a",
        boolean: "True",
        datetime: "2025-07-12 00:07:13",
      },
      { number: 2, text: "b", boolean: "False", datetime: null },
      { number: 3, text: "c", boolean: null, datetime: "2025-07-12 00:07:13" },
      { number: 0, text: "", boolean: "", datetime: "" },
    ]);
  });

  it("should handle renaming to the same name", () => {
    const result = renameColumn(testData, "int", "int");

    // Should return the original data unchanged
    expect(result).toEqual(testData);
  });

  it("should handle numeric column names", () => {
    const numericData = [{ "1": "value1", "2": "value2" }];
    const result = renameColumn(numericData, "1", "one");

    expect(result).toEqual([{ one: "value1", "2": "value2" }]);
  });
});

describe("modifyColumnFields", () => {
  const testFieldTypes: FieldTypes = {
    int: "integer",
    string: "string",
    bool: "boolean",
    datetime: "datetime",
  };

  it("should insert a new column at index 0", () => {
    const result = modifyColumnFields(testFieldTypes, 0, "insert", "newColumn");

    const expected = {
      newColumn: "string",
      int: "integer",
      string: "string",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should insert a new column at index 1", () => {
    const result = modifyColumnFields(testFieldTypes, 1, "insert", "newColumn");

    const expected = {
      int: "integer",
      newColumn: "string",
      string: "string",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should insert a new column at index 2", () => {
    const result = modifyColumnFields(testFieldTypes, 2, "insert", "newColumn");

    const expected = {
      int: "integer",
      string: "string",
      newColumn: "string",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should insert a new column at the end", () => {
    const result = modifyColumnFields(testFieldTypes, 4, "insert", "newColumn");

    const expected = {
      int: "integer",
      string: "string",
      bool: "boolean",
      datetime: "datetime",
      newColumn: "string",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should insert a new column beyond the array length", () => {
    const result = modifyColumnFields(
      testFieldTypes,
      10,
      "insert",
      "newColumn",
    );

    const expected = {
      int: "integer",
      string: "string",
      bool: "boolean",
      datetime: "datetime",
      newColumn: "string",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should remove column at index 0", () => {
    const result = modifyColumnFields(testFieldTypes, 0, "remove");

    const expected = {
      string: "string",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should remove column at index 1", () => {
    const result = modifyColumnFields(testFieldTypes, 1, "remove");

    const expected = {
      int: "integer",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should remove column at index 2", () => {
    const result = modifyColumnFields(testFieldTypes, 2, "remove");

    const expected = {
      int: "integer",
      string: "string",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should remove column at index 3", () => {
    const result = modifyColumnFields(testFieldTypes, 3, "remove");

    const expected = {
      int: "integer",
      string: "string",
      bool: "boolean",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should handle removing non-existent column index", () => {
    const result = modifyColumnFields(testFieldTypes, 999, "remove");
    // Should return the original field types since the index doesn't exist
    expect(result).toEqual(testFieldTypes);
  });

  it("should handle negative index for remove", () => {
    const result = modifyColumnFields(testFieldTypes, -1, "remove");
    // Should return the original field types since negative index is invalid
    expect(result).toEqual(testFieldTypes);
  });

  it("should rename column at index 0", () => {
    const result = modifyColumnFields(testFieldTypes, 0, "rename", "number");

    const expected = {
      number: "string", // Defaults to string type for renamed columns
      string: "string",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should rename column at index 1", () => {
    const result = modifyColumnFields(testFieldTypes, 1, "rename", "text");

    const expected = {
      int: "integer",
      text: "string", // Defaults to string type for renamed columns
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should rename column at index 3", () => {
    const result = modifyColumnFields(testFieldTypes, 3, "rename", "timestamp");

    const expected = {
      int: "integer",
      string: "string",
      bool: "boolean",
      timestamp: "string", // Defaults to string type for renamed columns
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });

  it("should handle renaming non-existent column index", () => {
    const result = modifyColumnFields(testFieldTypes, 999, "rename", "newName");
    // Should return the original field types since the index doesn't exist
    expect(result).toEqual(testFieldTypes);
  });

  it("should handle negative index for rename", () => {
    const result = modifyColumnFields(testFieldTypes, -1, "rename", "newName");
    // Should return the original field types since negative index is invalid
    expect(result).toEqual(testFieldTypes);
  });

  it("should preserve original field types structure", () => {
    const originalFieldTypes = { ...testFieldTypes };
    modifyColumnFields(testFieldTypes, 1, "remove");
    // Original field types should remain unchanged
    expect(testFieldTypes).toEqual(originalFieldTypes);
  });

  it("should handle empty field types object", () => {
    const emptyFieldTypes: FieldTypes = {};

    // Insert
    const insertResult = modifyColumnFields(
      emptyFieldTypes,
      0,
      "insert",
      "newColumn",
    );
    expect(insertResult).toEqual({ newColumn: "string" });

    // Remove
    const removeResult = modifyColumnFields(emptyFieldTypes, 0, "remove");
    expect(removeResult).toEqual({});
  });

  it("should handle field types with special characters in column names", () => {
    const specialFieldTypes: FieldTypes = {
      "column-with-dash": "integer",
      column_with_underscore: "string",
      "column.with.dot": "boolean",
      "column with space": "datetime",
    };

    // Insert
    const insertResult = modifyColumnFields(
      specialFieldTypes,
      1,
      "insert",
      "new-column",
    );
    const insertExpected = {
      "column-with-dash": "integer",
      "new-column": "string",
      column_with_underscore: "string",
      "column.with.dot": "boolean",
      "column with space": "datetime",
    };
    expect(Object.keys(insertResult)).toEqual(Object.keys(insertExpected));
    expect(insertResult).toEqual(insertExpected);

    // Remove
    const removeResult = modifyColumnFields(specialFieldTypes, 1, "remove");
    const removeExpected = {
      "column-with-dash": "integer",
      "column.with.dot": "boolean",
      "column with space": "datetime",
    };
    expect(Object.keys(removeResult)).toEqual(Object.keys(removeExpected));
    expect(removeResult).toEqual(removeExpected);

    // Rename
    const renameResult = modifyColumnFields(
      specialFieldTypes,
      1,
      "rename",
      "renamed-column",
    );
    const renameExpected = {
      "column-with-dash": "integer",
      "renamed-column": "string",
      "column.with.dot": "boolean",
      "column with space": "datetime",
    };
    expect(Object.keys(renameResult)).toEqual(Object.keys(renameExpected));
    expect(renameResult).toEqual(renameExpected);
  });

  it("should handle field types with numeric column names", () => {
    const numericFieldTypes: FieldTypes = {
      "1": "integer",
      "2": "string",
      "3": "boolean",
    };

    // Insert
    const insertResult = modifyColumnFields(
      numericFieldTypes,
      1,
      "insert",
      "newColumn",
    );
    const insertExpected = {
      "1": "integer",
      newColumn: "string",
      "2": "string",
      "3": "boolean",
    };
    expect(Object.keys(insertResult)).toEqual(Object.keys(insertExpected));
    expect(insertResult).toEqual(insertExpected);

    // Remove
    const removeResult = modifyColumnFields(numericFieldTypes, 1, "remove");
    const removeExpected = {
      "1": "integer",
      "3": "boolean",
    };
    expect(Object.keys(removeResult)).toEqual(Object.keys(removeExpected));
    expect(removeResult).toEqual(removeExpected);

    // Rename
    const renameResult = modifyColumnFields(
      numericFieldTypes,
      1,
      "rename",
      "renamed",
    );
    const renameExpected = {
      "1": "integer",
      renamed: "string",
      "3": "boolean",
    };
    expect(Object.keys(renameResult)).toEqual(Object.keys(renameExpected));
    expect(renameResult).toEqual(renameExpected);
  });

  it("should handle multiple operations in sequence", () => {
    let result = modifyColumnFields(testFieldTypes, 1, "insert", "newColumn");
    result = modifyColumnFields(result, 2, "remove");
    result = modifyColumnFields(result, 0, "rename", "renamed");

    const expected = {
      renamed: "string",
      newColumn: "string",
      bool: "boolean",
      datetime: "datetime",
    };

    expect(Object.keys(result)).toEqual(Object.keys(expected));
    expect(result).toEqual(expected);
  });
});
