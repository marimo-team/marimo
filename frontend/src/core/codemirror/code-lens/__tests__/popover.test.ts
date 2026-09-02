/* Copyright 2026 Marimo. All rights reserved. */

import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CodeLensSpec } from "../entities";

// Stable mock reference so every (re)import of popover.tsx after
// vi.resetModules() sees the same spy — the module-level fetch-throttle
// state in popover.tsx (`lastCacheInfoFetchAt`) needs to start fresh per
// test, which requires resetting the whole module, not just the mock.
const { getCacheInfoMock } = vi.hoisted(() => ({
  getCacheInfoMock: vi.fn().mockResolvedValue(null),
}));

vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => ({ getCacheInfo: getCacheInfoMock }),
}));

const CACHE_SPEC: CodeLensSpec = {
  pos: 0,
  kind: "cache",
  name: "my_cache",
  // `boundName: null` means the popover has no per-cache stats to fall back
  // on, so it always attempts the notebook-wide `getCacheInfo` fetch.
  cache: { boundName: null, cacheName: "my_cache" },
};

describe("CachePopover getCacheInfo throttling", () => {
  let mountLensPopover: typeof import("../popover").mountLensPopover;
  let now: number;

  beforeEach(async () => {
    vi.resetModules();
    getCacheInfoMock.mockClear();
    getCacheInfoMock.mockResolvedValue(null);
    ({ mountLensPopover } = await import("../popover"));
    // Control `Date.now()` directly (rather than `vi.useFakeTimers()`)
    // so React's own scheduler — which effect-flushing inside `act()`
    // depends on — keeps using real timers.
    now = 0;
    vi.spyOn(Date, "now").mockImplementation(() => now);
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  function mount() {
    const dom = document.createElement("div");
    document.body.append(dom);
    let dispose: () => void;
    act(() => {
      dispose = mountLensPopover(dom, CACHE_SPEC);
    });
    return () => act(() => dispose());
  }

  it("renders content synchronously for CodeMirror's initial measurement", async () => {
    const dom = document.createElement("div");

    // Keep the mount outside `act()`. It would flush an asynchronous render
    // and make this assertion pass without `flushSync`.
    const dispose = mountLensPopover(dom, CACHE_SPEC);

    expect(dom.textContent).toContain("my_cache");
    await act(async () => {
      dispose();
    });
  });

  it("does not refetch on every hover, only after the throttle interval elapses", () => {
    const disposeFirst = mount();
    expect(getCacheInfoMock).toHaveBeenCalledTimes(1);
    disposeFirst();

    // Hovering again shortly after should reuse whatever is already in
    // flight/cached rather than firing a second request.
    const disposeSecond = mount();
    expect(getCacheInfoMock).toHaveBeenCalledTimes(1);
    disposeSecond();

    now += 5001;

    const disposeThird = mount();
    expect(getCacheInfoMock).toHaveBeenCalledTimes(2);
    disposeThird();
  });

  it("allows an immediate retry after a failed fetch instead of waiting out the interval", async () => {
    getCacheInfoMock.mockRejectedValueOnce(new Error("kernel not ready"));

    const disposeFirst = mount();
    expect(getCacheInfoMock).toHaveBeenCalledTimes(1);
    // Flush the microtask queue so the effect's `.catch()` runs and resets
    // the throttle before the next hover.
    await act(async () => {
      await Promise.resolve();
    });
    disposeFirst();

    const disposeSecond = mount();
    expect(getCacheInfoMock).toHaveBeenCalledTimes(2);
    disposeSecond();
  });
});
