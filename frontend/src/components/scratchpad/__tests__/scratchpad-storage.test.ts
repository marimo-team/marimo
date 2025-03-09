/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { getStorageKey } from "../scratchpad-storage";

// This test file is intentionally kept minimal to avoid complex mocking
describe("scratchpad-storage", () => {
  it("should export the getStorageKey function", () => {
    expect(typeof getStorageKey).toBe("function");
  });
});
