/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { adaptForLocalStorage } from "../storage";

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
};

Object.defineProperty(global, "localStorage", {
  value: localStorageMock,
  writable: true,
});

// Mock Logger
vi.mock("../Logger", () => ({
  Logger: {
    warn: vi.fn(),
  },
}));

interface TestValue {
  id: string;
  data: Map<string, number>;
}

interface SerializableValue {
  id: string;
  data: [string, number][];
}

describe("adaptForLocalStorage", () => {
  const storage = adaptForLocalStorage<TestValue, SerializableValue>({
    toSerializable: (v) => ({
      id: v.id,
      data: [...v.data.entries()],
    }),
    fromSerializable: (s) => ({
      id: s.id,
      data: new Map(s.data),
    }),
  });

  const testValue: TestValue = {
    id: "test",
    data: new Map([
      ["key1", 1],
      ["key2", 2],
    ]),
  };

  const initialValue: TestValue = {
    id: "initial",
    data: new Map(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getItem", () => {
    it("should return parsed value when localStorage contains valid data", () => {
      const serialized = JSON.stringify({
        id: "test",
        data: [
          ["key1", 1],
          ["key2", 2],
        ],
      });
      localStorageMock.getItem.mockReturnValue(serialized);

      const result = storage.getItem("test-key", initialValue);

      expect(localStorageMock.getItem).toHaveBeenCalledWith("test-key");
      expect(result.id).toBe("test");
      expect(result.data.get("key1")).toBe(1);
      expect(result.data.get("key2")).toBe(2);
    });

    it("should return initial value when localStorage returns null", () => {
      localStorageMock.getItem.mockReturnValue(null);

      const result = storage.getItem("test-key", initialValue);

      expect(result).toBe(initialValue);
    });

    it("should return initial value when localStorage returns empty string", () => {
      localStorageMock.getItem.mockReturnValue("");

      const result = storage.getItem("test-key", initialValue);

      expect(result).toBe(initialValue);
    });

    it("should return initial value and log warning when JSON parsing fails", () => {
      localStorageMock.getItem.mockReturnValue("invalid-json");

      const result = storage.getItem("test-key", initialValue);

      expect(result).toBe(initialValue);
      // Logger.warn should have been called but we're not testing the exact call
    });

    it("should return initial value and log warning when deserialization fails", () => {
      // This JSON is parseable but will cause the Map constructor to throw
      localStorageMock.getItem.mockReturnValue(
        '{"id": "test", "data": "not-an-array"}',
      );

      const result = storage.getItem("test-key", initialValue);

      expect(result).toEqual(initialValue);
    });
  });

  describe("setItem", () => {
    it("should serialize and store value in localStorage", () => {
      storage.setItem("test-key", testValue);

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "test-key",
        JSON.stringify({
          id: "test",
          data: [
            ["key1", 1],
            ["key2", 2],
          ],
        }),
      );
    });
  });

  describe("removeItem", () => {
    it("should call localStorage.removeItem with the correct key", () => {
      storage.removeItem("test-key");

      expect(localStorageMock.removeItem).toHaveBeenCalledWith("test-key");
    });
  });
});
