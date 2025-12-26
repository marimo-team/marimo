/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CachingRequestRegistry } from "../CachingRequestRegistry";
import {
  DeferredRequestRegistry,
  type RequestId,
} from "../DeferredRequestRegistry";

vi.mock("@/utils/uuid", () => ({
  generateUUID: vi.fn().mockReturnValue("uuid"),
}));

describe("CachingRequestRegistry", () => {
  const REQUEST_ID = "uuid" as RequestId;
  let makeRequestMock = vi.fn();
  let delegate: DeferredRequestRegistry<unknown, unknown>;
  let caching: CachingRequestRegistry<unknown, unknown>;

  beforeEach(() => {
    makeRequestMock = vi.fn().mockResolvedValue(undefined);
    delegate = new DeferredRequestRegistry("operation", makeRequestMock);
    caching = new CachingRequestRegistry(delegate);
  });

  it("should cache successful responses for identical requests", async () => {
    const req = { a: 1 };

    const p1 = caching.request(req);
    expect(makeRequestMock).toHaveBeenCalledTimes(1);
    expect(makeRequestMock).toHaveBeenCalledWith(REQUEST_ID, req);

    // Resolve first request
    delegate.resolve(REQUEST_ID, "response");
    await expect(p1).resolves.toBe("response");

    // Second call with equivalent request gets served from cache
    const p2 = caching.request({ a: 1 });
    expect(makeRequestMock).toHaveBeenCalledTimes(1);
    await expect(p2).resolves.toBe("response");
  });

  it("should de-duplicate in-flight requests with the same key", async () => {
    const req = { q: "select *" };

    const p1 = caching.request(req);
    const p2 = caching.request({ q: "select *" });

    // Only one network invocation while in-flight
    expect(makeRequestMock).toHaveBeenCalledTimes(1);
    expect(p1).toStrictEqual(p2);

    // Resolve and ensure both resolve to same result
    delegate.resolve(REQUEST_ID, "ok");
    await expect(p1).resolves.toBe("ok");
    await expect(p2).resolves.toBe("ok");
  });

  it("should not cache errors", async () => {
    // First call rejects
    makeRequestMock.mockRejectedValueOnce(new Error("boom"));

    await expect(caching.request({ x: 1 })).rejects.toThrow("boom");
    expect(makeRequestMock).toHaveBeenCalledTimes(1);

    // Next call should attempt again (not cached)
    const p2 = caching.request({ x: 1 });
    expect(makeRequestMock).toHaveBeenCalledTimes(2);

    // Resolve the second request
    delegate.resolve(REQUEST_ID, "ok");
    await expect(p2).resolves.toBe("ok");
  });
});
