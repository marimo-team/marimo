/* Copyright 2026 Marimo. All rights reserved. */
import { act, render, renderHook, waitFor } from "@testing-library/react";
import { Activity } from "react";
import { describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { useAsyncData } from "../useAsyncData";

function AsyncDataStatus({ fetch }: { fetch: () => Promise<string> }) {
  const result = useAsyncData(fetch, []);
  return (
    <output
      data-status={result.status}
      data-fetching={result.isFetching}
      data-error={result.error?.message ?? ""}
    >
      {result.data}
    </output>
  );
}

describe("useAsyncData", () => {
  it.each(["success", "error"] as const)(
    "restarts fetching when Activity reopens after %s",
    async (initialStatus) => {
      const initial = new Deferred<string>();
      const restarted = new Deferred<string>();
      const fetch = vi
        .fn(() => restarted.promise)
        .mockImplementationOnce(() => initial.promise);
      const view = render(
        <Activity mode="visible">
          <AsyncDataStatus fetch={fetch} />
        </Activity>,
      );
      await act(async () => {
        if (initialStatus === "success") {
          initial.resolve("first");
        } else {
          initial.reject(new Error("offline"));
        }
      });
      expect(view.getByRole("status").dataset.status).toBe(initialStatus);

      view.rerender(
        <Activity mode="hidden">
          <AsyncDataStatus fetch={fetch} />
        </Activity>,
      );
      view.rerender(
        <Activity mode="visible">
          <AsyncDataStatus fetch={fetch} />
        </Activity>,
      );

      expect(fetch).toHaveBeenCalledTimes(2);
      expect(view.getByRole("status").dataset).toMatchObject({
        status: initialStatus === "success" ? "loading" : "pending",
        error: "",
        fetching: "true",
      });
      expect(view.getByRole("status").textContent).toBe(
        initialStatus === "success" ? "first" : "",
      );
      await act(async () => restarted.resolve("latest"));
      expect(view.getByRole("status").dataset).toMatchObject({
        status: "success",
        fetching: "false",
      });
      expect(view.getByRole("status").textContent).toBe("latest");
    },
  );

  it("ignores a request canceled when Activity hides", async () => {
    const canceled = new Deferred<string>();
    const restarted = new Deferred<string>();
    const fetch = vi
      .fn(() => restarted.promise)
      .mockImplementationOnce(() => canceled.promise);
    const view = render(
      <Activity mode="visible">
        <AsyncDataStatus fetch={fetch} />
      </Activity>,
    );
    view.rerender(
      <Activity mode="hidden">
        <AsyncDataStatus fetch={fetch} />
      </Activity>,
    );
    view.rerender(
      <Activity mode="visible">
        <AsyncDataStatus fetch={fetch} />
      </Activity>,
    );
    expect(fetch).toHaveBeenCalledTimes(2);
    await act(async () => canceled.resolve("obsolete"));
    expect(view.getByRole("status").dataset.status).toBe("pending");
    expect(view.getByRole("status").textContent).toBe("");
    await act(async () => restarted.resolve("latest"));
    expect(view.getByRole("status").dataset.status).toBe("success");
    expect(view.getByRole("status").textContent).toBe("latest");
  });

  it("preserves data while refetching and ignores obsolete requests", async () => {
    const requests = [
      new Deferred<string>(),
      new Deferred<string>(),
      new Deferred<string>(),
    ];
    const fetch = vi
      .fn(() => requests[0].promise)
      .mockImplementationOnce(() => requests[0].promise)
      .mockImplementationOnce(() => requests[1].promise)
      .mockImplementationOnce(() => requests[2].promise);
    const { result, rerender } = renderHook(
      ({ key }) => useAsyncData(fetch, [key]),
      { initialProps: { key: 0 } },
    );
    expect(result.current.status).toBe("pending");
    await act(async () => requests[0].resolve("first"));
    expect(result.current.data).toBe("first");
    rerender({ key: 1 });
    expect(result.current).toMatchObject({ status: "loading", data: "first" });
    rerender({ key: 2 });
    await act(async () => requests[1].resolve("obsolete"));
    expect(result.current).toMatchObject({ status: "loading", data: "first" });
    await act(async () => requests[2].resolve("latest"));
    expect(result.current).toMatchObject({ status: "success", data: "latest" });
  });

  it("retries after errors and allows manual updates during a request", async () => {
    const request = new Deferred<string>();
    const fetch = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockImplementation(() => request.promise);
    const { result } = renderHook(() => useAsyncData(fetch, []));
    await waitFor(() => expect(result.current.status).toBe("error"));
    act(() => result.current.refetch());
    expect(result.current.status).toBe("pending");
    act(() => result.current.setData("manual"));
    expect(result.current).toMatchObject({ status: "success", data: "manual" });
    await act(async () => request.resolve("response"));
    expect(result.current).toMatchObject({
      status: "success",
      data: "response",
    });
  });
});
