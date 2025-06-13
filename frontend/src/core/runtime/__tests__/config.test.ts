/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, type Mocked, vi } from "vitest";
import { store } from "@/core/state/jotai";
import { asRemoteURL, getRuntimeManager } from "../config";
import type { RuntimeManager } from "../runtime";

// Mock the store
vi.mock("@/core/state/jotai", () => ({
  store: {
    get: vi.fn(),
  },
}));

// Mock the RuntimeManager
vi.mock("../runtime", () => ({
  RuntimeManager: vi.fn(),
}));

// Mock jotai hooks
vi.mock("jotai", () => ({
  atom: vi.fn((value) => ({ init: value })),
  useAtomValue: vi.fn(),
}));

const mockedStore = store as Mocked<typeof store>;

describe("runtime config", () => {
  const mockRuntimeManager = {
    httpURL: new URL("http://localhost:8080"),
  } as RuntimeManager;

  beforeEach(() => {
    vi.clearAllMocks();
    mockedStore.get.mockReturnValue(mockRuntimeManager);
  });

  describe("asRemoteURL", () => {
    it("should return URL as-is for absolute HTTP URLs", () => {
      const result = asRemoteURL("https://example.com/data.csv");
      expect(result.toString()).toBe("https://example.com/data.csv");
    });

    it("should return URL as-is for absolute HTTPS URLs", () => {
      const result = asRemoteURL("https://example.com/api/data");
      expect(result.toString()).toBe("https://example.com/api/data");
    });

    it("should resolve relative paths against runtime manager base URL", () => {
      const result = asRemoteURL("/api/data");
      expect(result.toString()).toBe("http://localhost:8080/api/data");
    });

    it("should handle relative paths without leading slash", () => {
      const result = asRemoteURL("api/data");
      expect(result.toString()).toBe("http://localhost:8080/api/data");
    });

    it("should handle file paths", () => {
      const result = asRemoteURL("/@file/data.csv");
      expect(result.toString()).toBe("http://localhost:8080/@file/data.csv");
    });

    it("should handle data URLs", () => {
      const dataURL = "data:text/csv;base64,YSxiLGMKMSwyLDM=";
      const result = asRemoteURL(dataURL);
      expect(result.toString()).toBe(dataURL);
    });

    it("should handle empty paths", () => {
      const result = asRemoteURL("");
      expect(result.toString()).toBe("http://localhost:8080/");
    });

    it("should handle query parameters", () => {
      const result = asRemoteURL("/api/data?param=value");
      expect(result.toString()).toBe(
        "http://localhost:8080/api/data?param=value",
      );
    });

    it("should handle fragments", () => {
      const result = asRemoteURL("/api/data#section");
      expect(result.toString()).toBe("http://localhost:8080/api/data#section");
    });

    it("should handle complex relative paths", () => {
      const result = asRemoteURL("./api/../data/file.csv");
      expect(result.toString()).toBe("http://localhost:8080/data/file.csv");
    });

    it("should handle URLs with different base paths", () => {
      const customRuntimeManager = {
        httpURL: new URL("https://custom.marimo.io/app/"),
      } as RuntimeManager;
      mockedStore.get.mockReturnValue(customRuntimeManager);

      const result = asRemoteURL("/api/data");
      expect(result.toString()).toBe("https://custom.marimo.io/api/data");
    });
  });

  describe("getRuntimeManager", () => {
    it("should return runtime manager from store", () => {
      const result = getRuntimeManager();
      expect(result).toBe(mockRuntimeManager);
      expect(store.get).toHaveBeenCalled();
    });
  });

  describe("edge cases", () => {
    it("should handle malformed URLs gracefully", () => {
      expect(() => asRemoteURL("not a url with spaces")).not.toThrow();
    });

    it("should handle URLs with unusual protocols", () => {
      const result = asRemoteURL("ftp://example.com/file.txt");
      expect(result.toString()).toBe("ftp://example.com/file.txt");
    });

    it("should handle localhost URLs", () => {
      const result = asRemoteURL("http://localhost:3000/api");
      expect(result.toString()).toBe("http://localhost:3000/api");
    });

    it("should handle IP address URLs", () => {
      const result = asRemoteURL("http://192.168.1.1:8080/api");
      expect(result.toString()).toBe("http://192.168.1.1:8080/api");
    });
  });

  describe("runtime manager integration", () => {
    it("should work with different runtime manager base URLs", () => {
      const testCases = [
        {
          baseURL: "http://localhost:8080",
          path: "/api",
          expected: "http://localhost:8080/api",
        },
        {
          baseURL: "https://marimo.app",
          path: "/data",
          expected: "https://marimo.app/data",
        },
        {
          baseURL: "http://192.168.1.1:3000",
          path: "files",
          expected: "http://192.168.1.1:3000/files",
        },
      ];

      testCases.forEach(({ baseURL, path, expected }) => {
        const customManager = { httpURL: new URL(baseURL) } as RuntimeManager;
        mockedStore.get.mockReturnValue(customManager);

        const result = asRemoteURL(path);
        expect(result.toString()).toBe(expected);
      });
    });
  });
});
