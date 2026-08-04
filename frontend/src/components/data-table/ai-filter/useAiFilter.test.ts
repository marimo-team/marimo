/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FieldTypesWithExternalType } from "../types";
import { requestAiFilterQuery } from "./request";
import { useAiFilter } from "./useAiFilter";

vi.mock("@/core/runtime/config", () => ({
  useRuntimeManager: vi.fn(() => ({})),
}));

vi.mock("./request", () => ({
  requestAiFilterQuery: vi.fn(),
}));

const fieldTypes: FieldTypesWithExternalType = [
  ["status", ["string", "object"]],
];

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason?: unknown) => void = () => undefined;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("useAiFilter", () => {
  beforeEach(() => {
    vi.mocked(requestAiFilterQuery).mockReset();
  });

  it("keeps the latest generation when requests resolve out of order", async () => {
    const older = deferred<string>();
    const latest = deferred<string>();
    vi.mocked(requestAiFilterQuery)
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(latest.promise);
    const { result } = renderHook(() => useAiFilter(fieldTypes));

    let olderGeneration: Promise<void>;
    let latestGeneration: Promise<void>;
    act(() => {
      olderGeneration = result.current.generate("open issues");
      latestGeneration = result.current.generate("closed issues");
    });

    await act(async () => {
      latest.resolve("status:closed");
      await latestGeneration;
    });
    expect(result.current.rawQuery).toBe("status:closed");
    expect(result.current.appliedRaw).toBe("status:closed");
    expect(result.current.generationId).toBe(1);

    await act(async () => {
      older.resolve("status:open");
      await olderGeneration;
    });
    expect(result.current.rawQuery).toBe("status:closed");
    expect(result.current.appliedRaw).toBe("status:closed");
    expect(result.current.generationId).toBe(1);
    expect(result.current.isGenerating).toBe(false);
  });

  it("ignores an in-flight generation after the filter is cleared", async () => {
    const pending = deferred<string>();
    vi.mocked(requestAiFilterQuery).mockReturnValueOnce(pending.promise);
    const { result } = renderHook(() => useAiFilter(fieldTypes));

    let generation: Promise<void>;
    act(() => {
      generation = result.current.generate("open issues");
    });
    expect(result.current.isActive).toBe(true);
    expect(result.current.isGenerating).toBe(true);

    act(() => result.current.clear());
    expect(result.current.isActive).toBe(false);
    expect(result.current.isGenerating).toBe(false);

    await act(async () => {
      pending.resolve("status:open");
      await generation;
    });
    expect(result.current.rawQuery).toBe("");
    expect(result.current.appliedRaw).toBe("");
    expect(result.current.generationId).toBe(0);
  });
});
