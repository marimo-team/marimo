/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { storageAtom, useStorageEntries } from "../state";
import type { StorageEntry, StorageState } from "../types";

const mockRequest = vi.fn();

vi.mock("../request-registry", () => ({
  ListStorageEntries: {
    request: (...args: unknown[]) => mockRequest(...args),
  },
}));

function makeEntry(
  overrides: Partial<StorageEntry> & { path: string },
): StorageEntry {
  return {
    kind: overrides.kind ?? "file",
    lastModified: overrides.lastModified ?? null,
    metadata: overrides.metadata ?? {},
    path: overrides.path,
    size: overrides.size ?? 0,
  };
}

describe("useStorageEntries", () => {
  let store: ReturnType<typeof createStore>;

  const wrapper = ({ children }: { children: ReactNode }) =>
    React.createElement(Provider, { store }, children);

  beforeEach(() => {
    vi.clearAllMocks();
    store = createStore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function setStorageState(state: Partial<StorageState>) {
    const current = store.get(storageAtom);
    store.set(storageAtom, { ...current, ...state });
  }

  it("should fetch entries when not cached", async () => {
    const entries = [
      makeEntry({ path: "a.txt" }),
      makeEntry({ path: "b.txt" }),
    ];
    mockRequest.mockResolvedValue({ entries });

    const { result } = renderHook(() => useStorageEntries("my_s3", "data/"), {
      wrapper,
    });

    expect(result.current.isPending).toBe(true);
    expect(result.current.entries).toEqual([]);

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(result.current.entries).toEqual(entries);
    expect(mockRequest).toHaveBeenCalledWith({
      namespace: "my_s3",
      prefix: "data/",
      limit: 150,
    });
  });

  it("should return cached entries without fetching", async () => {
    const entries = [makeEntry({ path: "cached.txt" })];
    setStorageState({
      entriesByPath: new Map([["my_s3::data/", entries]]),
    });

    const { result } = renderHook(() => useStorageEntries("my_s3", "data/"), {
      wrapper,
    });

    expect(result.current.entries).toEqual(entries);
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeUndefined();
    expect(mockRequest).not.toHaveBeenCalled();
  });

  it("should normalize null prefix to empty string", async () => {
    const entries = [makeEntry({ path: "root.txt" })];
    mockRequest.mockResolvedValue({ entries });

    const { result } = renderHook(() => useStorageEntries("ns"), { wrapper });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(result.current.entries).toEqual(entries);
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ prefix: "" }),
    );
  });

  it("should normalize undefined prefix to empty string", async () => {
    const entries = [makeEntry({ path: "root.txt" })];
    mockRequest.mockResolvedValue({ entries });

    const { result } = renderHook(() => useStorageEntries("ns", undefined), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ prefix: "" }),
    );
  });

  it("should return the error when fetch fails and nothing is cached", async () => {
    mockRequest.mockRejectedValue(new Error("network failure"));

    const { result } = renderHook(() => useStorageEntries("ns", "pfx/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.error).toBeDefined();
    });

    expect(result.current.error?.message).toBe("network failure");
    expect(result.current.entries).toEqual([]);
    expect(result.current.isPending).toBe(false);
  });

  it("should surface result.error as a thrown error", async () => {
    mockRequest.mockResolvedValue({
      entries: [],
      error: "access denied",
    });

    const { result } = renderHook(() => useStorageEntries("ns", "pfx/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.error).toBeDefined();
    });

    expect(result.current.error?.message).toBe("access denied");
    expect(result.current.entries).toEqual([]);
    expect(result.current.isPending).toBe(false);
  });

  it("should suppress error when entries are cached", async () => {
    const entries = [makeEntry({ path: "ok.txt" })];
    setStorageState({
      entriesByPath: new Map([["ns::pfx/", entries]]),
    });

    const { result } = renderHook(() => useStorageEntries("ns", "pfx/"), {
      wrapper,
    });

    expect(result.current.error).toBeUndefined();
    expect(result.current.entries).toEqual(entries);
    expect(result.current.isPending).toBe(false);
  });

  it("should store fetched entries in the atom", async () => {
    const entries = [makeEntry({ path: "new.txt" })];
    mockRequest.mockResolvedValue({ entries });

    renderHook(() => useStorageEntries("ns", "sub/"), { wrapper });

    await waitFor(() => {
      const state = store.get(storageAtom);
      expect(state.entriesByPath.get("ns::sub/")).toEqual(entries);
    });
  });
});
