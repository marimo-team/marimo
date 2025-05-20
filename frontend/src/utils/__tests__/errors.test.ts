/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { prettyError } from "../errors";

describe("prettyError", () => {
  it("handles null/undefined errors", () => {
    expect(prettyError(null)).toBe("Unknown error");
    expect(prettyError(undefined)).toBe("Unknown error");
  });

  it("extracts details from Error objects with cause", () => {
    const error = new Error("Original message");
    error.cause = { detail: "Detailed error message" };
    expect(prettyError(error)).toBe("Detailed error message");
  });

  it("extracts details from Error objects with error", () => {
    const error = { error: "Detailed error message" };
    expect(prettyError(error)).toBe("Detailed error message");
  });

  it("extracts details from Error message if JSON", () => {
    const error = new Error('{"detail": "JSON error message"}');
    expect(prettyError(error)).toBe("JSON error message");
  });

  it("returns original message if not JSON", () => {
    const error = new Error("Plain error message");
    expect(prettyError(error)).toBe("Plain error message");
  });

  it("handles objects with detail property", () => {
    const error = { detail: "Object error message" };
    expect(prettyError(error)).toBe("Object error message");
  });

  it("stringifies plain objects", () => {
    const error = { foo: "bar" };
    expect(prettyError(error)).toBe('{"foo":"bar"}');
  });

  it("handles primitive values", () => {
    expect(prettyError(123)).toBe("123");
    expect(prettyError("string error")).toBe('"string error"');
    expect(prettyError(true)).toBe("true");
  });

  it("handles circular references", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const circular: any = { foo: "bar" };
    circular.self = circular;
    expect(prettyError(circular)).toBe("[object Object]");
  });
});
