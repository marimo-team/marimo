/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { combineAsyncData, useAsyncData } from "../useAsyncData";

describe("useAsyncData error recovery", () => {
  it.each([undefined, 0, 3])(
    "retains error and data (%s) through repeated retries",
    async (data) => {
      const error = new Error(
        "Step 1 (Sample Rows): dataframe contains 3 rows",
      );
      const retry = new Deferred<number>();
      const recovery = new Deferred<number>();
      const fetch = vi.fn<() => Promise<number>>();
      if (data !== undefined) {
        fetch.mockResolvedValueOnce(data);
      }
      fetch
        .mockRejectedValueOnce(error)
        .mockReturnValueOnce(retry.promise)
        .mockReturnValueOnce(recovery.promise);
      const { result } = renderHook(() => useAsyncData(fetch, []));
      if (data !== undefined) {
        await waitFor(() => expect(result.current.status).toBe("success"));
        act(() => result.current.refetch());
      }
      await waitFor(() => expect(result.current.status).toBe("error"));
      const expected = {
        status: "error",
        data,
        error,
        isPending: false,
        isFetching: false,
        refetch: expect.any(Function),
        setData: expect.any(Function),
      };
      expect(result.current).toEqual(expected);

      act(() => result.current.refetch());
      expect(result.current).toEqual({ ...expected, isFetching: true });
      expect(combineAsyncData(result.current).isFetching).toBe(true);

      await act(async () => retry.reject(error));
      expect(result.current).toEqual(expected);

      act(() => result.current.refetch());
      expect(result.current).toEqual({ ...expected, isFetching: true });
      await act(async () => recovery.resolve(2));
      expect(result.current).toEqual({
        ...expected,
        status: "success",
        data: 2,
        error: undefined,
      });
    },
  );

  it("ignores an obsolete retry after a newer request succeeds", async () => {
    const retry = new Deferred<number>();
    const fetch = vi
      .fn<() => Promise<number>>()
      .mockRejectedValueOnce(new Error("failed"))
      .mockReturnValueOnce(retry.promise)
      .mockResolvedValueOnce(2);
    const { result, rerender } = renderHook(
      ({ value }) => useAsyncData(fetch, [value]),
      {
        initialProps: { value: 0 },
      },
    );
    await waitFor(() => expect(result.current.status).toBe("error"));
    rerender({ value: 1 });
    rerender({ value: 2 });
    await waitFor(() => expect(result.current.status).toBe("success"));
    await act(async () => retry.reject(new Error("obsolete")));
    expect(result.current.data).toBe(2);
    expect(result.current.error).toBeUndefined();
  });
});
