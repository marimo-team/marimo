/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { exportedForTesting } from "../languages/sql/banner-validation-errors";

describe("Error Message Splitting", () => {
  it("should handle error message splitting correctly", () => {
    const { splitErrorMessage } = exportedForTesting;

    const result1 = splitErrorMessage("Syntax error: unexpected token");
    expect(result1.errorType).toBe("Syntax error");
    expect(result1.errorMessage).toBe("unexpected token");

    const result2 = splitErrorMessage("Multiple: colons: in error");
    expect(result2.errorType).toBe("Multiple");
    expect(result2.errorMessage).toBe("colons: in error");

    const result3 = splitErrorMessage("No colon error");
    expect(result3.errorType).toBe("No colon error");
    expect(result3.errorMessage).toBe("");
  });
});

describe("DuckDB Error Handling", () => {
  it("should extract codeblock from error with LINE information", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error =
      'Binder Error: Referenced column "attacks" not found in FROM clause! Candidate bindings: "Attack", "Total" LINE 1:... from pokemon WHERE \'type_2\' = 32 and attack = 32 and not attacks = \'hi\' ^';

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("Binder Error");
    expect(result.errorMessage).toBe(
      'Referenced column "attacks" not found in FROM clause! Candidate bindings: "Attack", "Total"',
    );
    expect(result.codeblock).toBe(
      "LINE 1:... from pokemon WHERE 'type_2' = 32 and attack = 32 and not attacks = 'hi' ^",
    );
  });

  it("should handle error without LINE information", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error = "Syntax Error: Invalid syntax near WHERE";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("Syntax Error");
    expect(result.errorMessage).toBe("Invalid syntax near WHERE");
    expect(result.codeblock).toBeUndefined();
  });

  it("should handle error with LINE at the beginning", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error = "LINE 1: SELECT * FROM table WHERE invalid_column = 1 ^";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("LINE 1");
    expect(result.errorMessage).toBe(
      "SELECT * FROM table WHERE invalid_column = 1 ^",
    );
    expect(result.codeblock).toBeUndefined();
  });

  it("should handle error with multiple LINE occurrences", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error =
      "Error: Something went wrong LINE 1: SELECT * FROM table WHERE invalid_column = 1 ^";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("Error");
    expect(result.errorMessage).toBe("Something went wrong");
    expect(result.codeblock).toBe(
      "LINE 1: SELECT * FROM table WHERE invalid_column = 1 ^",
    );
  });

  it("should handle complex error with nested quotes", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error =
      "Binder Error: Column \"name\" not found! LINE 1: SELECT * FROM users WHERE name = 'John' AND age > 25 ^";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("Binder Error");
    expect(result.errorMessage).toBe('Column "name" not found!');
    expect(result.codeblock).toBe(
      "LINE 1: SELECT * FROM users WHERE name = 'John' AND age > 25 ^",
    );
  });

  it("should handle error with LINE but no caret", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error = "Error: Invalid query LINE 1: SELECT * FROM table";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("Error");
    expect(result.errorMessage).toBe("Invalid query");
    expect(result.codeblock).toBe("LINE 1: SELECT * FROM table");
  });

  it("should trim whitespace from codeblock", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error = "Error: Something wrong   LINE 1: SELECT * FROM table   ^   ";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("Error");
    expect(result.errorMessage).toBe("Something wrong");
    expect(result.codeblock).toBe("LINE 1: SELECT * FROM table   ^");
  });

  it("should handle empty error message", () => {
    const { handleDuckdbError } = exportedForTesting;

    const error = "";

    const result = handleDuckdbError(error);

    expect(result.errorType).toBe("");
    expect(result.errorMessage).toBe("");
    expect(result.codeblock).toBeUndefined();
  });
});
