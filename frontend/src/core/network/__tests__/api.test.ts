/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { API } from "../api";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Default mock for getRuntimeManager
let baseUrl = "http://localhost:8000";
vi.mock("@/core/runtime/config", () => ({
  getRuntimeManager: () => ({
    get httpURL() {
      return new URL(baseUrl);
    },
    headers: () => ({}),
  }),
}));

describe("API", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    baseUrl = "http://localhost:8000";
  });

  it("API.post calls fetch with POST and correct URL", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.post("/foo", { bar: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/foo",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("API.get calls fetch with GET and correct URL", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.get("/bar");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/bar",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("API.post handles base URL with path correctly", async () => {
    baseUrl = "http://example.com/e";
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.post("/foo", { bar: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://example.com/e/api/foo",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("API.post handles base URL with trailing slash correctly", async () => {
    baseUrl = "http://example.com/e/";
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.post("/foo", { bar: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://example.com/e/api/foo",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
