/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useScript } from "../useScript";

afterEach(() => {
  document.querySelectorAll("script").forEach((script) => script.remove());
});

describe("useScript", () => {
  it("observes loading and completion of a new script", async () => {
    const { result } = renderHook(() => useScript("/first.js"));
    expect(result.current).toBe("loading");
    await act(async () => {
      document.querySelector("script")?.dispatchEvent(new Event("load"));
    });
    expect(result.current).toBe("ready");
  });

  it("uses the new source's status when the source changes", async () => {
    const { result, rerender } = renderHook(({ src }) => useScript(src), {
      initialProps: { src: "/first.js" },
    });
    await act(async () => {
      document.querySelector("script")?.dispatchEvent(new Event("load"));
    });
    expect(result.current).toBe("ready");
    rerender({ src: "/second.js" });
    expect(result.current).toBe("loading");
    await act(async () => {
      document
        .querySelector('script[src="/second.js"]')
        ?.dispatchEvent(new Event("error"));
    });
    expect(result.current).toBe("error");
  });

  it("shares an existing script and only removes scripts it owns", async () => {
    const owner = renderHook(() =>
      useScript("/first.js", { removeOnUnmount: true }),
    );
    const subscriber = renderHook(() =>
      useScript("/first.js", { removeOnUnmount: true }),
    );
    expect(document.querySelectorAll("script")).toHaveLength(1);
    await act(async () => {
      document.querySelector("script")?.dispatchEvent(new Event("load"));
    });
    expect(subscriber.result.current).toBe("ready");
    subscriber.unmount();
    expect(document.querySelectorAll("script")).toHaveLength(1);
    owner.unmount();
    expect(document.querySelectorAll("script")).toHaveLength(0);
  });

  it("settles for remaining subscribers when the first unmounts mid-load", async () => {
    const first = renderHook(() => useScript("/shared.js"));
    const second = renderHook(() => useScript("/shared.js"));
    first.unmount();
    expect(second.result.current).toBe("loading");
    await act(async () => {
      document.querySelector("script")?.dispatchEvent(new Event("load"));
    });
    expect(second.result.current).toBe("ready");
    // A later subscriber sees the settled status
    expect(renderHook(() => useScript("/shared.js")).result.current).toBe(
      "ready",
    );
  });

  it("handles sources that are not valid inside a CSS selector", () => {
    const src = '/odd"name].js';
    const { result } = renderHook(() => useScript(src));
    expect(result.current).toBe("loading");
    expect(document.querySelector("script")?.getAttribute("src")).toBe(src);
  });
});
