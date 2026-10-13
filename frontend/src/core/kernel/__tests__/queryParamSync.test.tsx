/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { requestClientAtom } from "@/core/network/requests";
import { Logger } from "@/utils/Logger";
import {
  parseSearchParams,
  syncQueryParamsOnNavigation,
} from "../queryParamSync";
import { useSyncQueryParamsOnNavigation } from "../useSyncQueryParamsOnNavigation";

function navigateTo(search: string) {
  const url = new URL("http://localhost:3000/");
  url.search = search;
  window.history.pushState({}, "", `${url.pathname}${url.search}`);
}

function fireBackNavigation() {
  // Only user navigation (back/forward) fires popstate, never pushState.
  window.dispatchEvent(new PopStateEvent("popstate"));
}

afterEach(() => {
  navigateTo("");
});

describe("parseSearchParams", () => {
  it("returns an empty record for no params", () => {
    expect(parseSearchParams("")).toEqual({});
    expect(parseSearchParams("?")).toEqual({});
  });

  it("maps a key that appears once to a string", () => {
    expect(parseSearchParams("?tab=plots&page=2")).toEqual({
      tab: "plots",
      page: "2",
    });
  });

  it("maps a repeated key to a list, like the kernel does", () => {
    expect(parseSearchParams("?ids=1&tab=a&ids=2&ids=3")).toEqual({
      ids: ["1", "2", "3"],
      tab: "a",
    });
  });

  it("decodes values and keeps empty values", () => {
    expect(parseSearchParams("?q=hello%20world&name=a+b&empty=")).toEqual({
      q: "hello world",
      name: "a b",
      empty: "",
    });
  });
});

describe("syncQueryParamsOnNavigation", () => {
  it("sends the restored URL's params to the kernel on popstate", () => {
    const send = vi.fn().mockResolvedValue(null);
    const stop = syncQueryParamsOnNavigation(send);

    navigateTo("?tab=b&ids=1&ids=2");
    fireBackNavigation();

    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith({
      queryParams: { tab: "b", ids: ["1", "2"] },
    });
    stop();
  });

  it("sends an empty record when navigating back to a bare URL", () => {
    const send = vi.fn().mockResolvedValue(null);
    const stop = syncQueryParamsOnNavigation(send);

    navigateTo("");
    fireBackNavigation();

    expect(send).toHaveBeenCalledWith({ queryParams: {} });
    stop();
  });

  it("does not send on pushState, only on navigation", () => {
    const send = vi.fn().mockResolvedValue(null);
    const stop = syncQueryParamsOnNavigation(send);

    navigateTo("?tab=b");

    expect(send).not.toHaveBeenCalled();
    stop();
  });

  it("stops listening once the returned cleanup runs", () => {
    const send = vi.fn().mockResolvedValue(null);
    const stop = syncQueryParamsOnNavigation(send);
    stop();

    navigateTo("?tab=b");
    fireBackNavigation();

    expect(send).not.toHaveBeenCalled();
  });

  it("logs instead of throwing when the request fails", async () => {
    const warn = vi.spyOn(Logger, "warn").mockImplementation(() => undefined);
    const send = vi.fn().mockRejectedValue(new Error("offline"));
    const stop = syncQueryParamsOnNavigation(send);

    navigateTo("?tab=b");
    expect(() => fireBackNavigation()).not.toThrow();
    // Let the rejected promise settle; an unhandled rejection would fail
    // the test run.
    await Promise.resolve();
    expect(warn).toHaveBeenCalledTimes(1);
    stop();
    warn.mockRestore();
  });
});

describe("useSyncQueryParamsOnNavigation", () => {
  it("wires the request client for the lifetime of the component", () => {
    const store = createStore();
    const client = MockRequestClient.create();
    store.set(requestClientAtom, client);
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );

    const { unmount } = renderHook(() => useSyncQueryParamsOnNavigation(), {
      wrapper,
    });
    navigateTo("?tab=b");
    fireBackNavigation();
    expect(client.sendUpdateQueryParams).toHaveBeenCalledWith({
      queryParams: { tab: "b" },
    });

    unmount();
    fireBackNavigation();
    expect(client.sendUpdateQueryParams).toHaveBeenCalledTimes(1);
  });
});
