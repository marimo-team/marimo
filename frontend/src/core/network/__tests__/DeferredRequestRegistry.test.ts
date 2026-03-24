/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { requestId } from "@/__tests__/branded";
import { DeferredRequestRegistry } from "../DeferredRequestRegistry";

vi.mock("@/utils/uuid", () => ({
  generateUUID: vi.fn().mockReturnValue("uuid"),
}));

describe("DeferredRequestRegistry", () => {
  const REQUEST_ID = requestId("uuid");
  let makeRequestMock = vi.fn();
  let registry: DeferredRequestRegistry<unknown, unknown>;

  beforeEach(() => {
    makeRequestMock = vi.fn().mockResolvedValue(undefined);
    registry = new DeferredRequestRegistry("operation", makeRequestMock);
  });

  it("should create and resolve new request", async () => {
    const promise = registry.request("requestOptions");
    expect(makeRequestMock).toHaveBeenCalledWith("uuid", "requestOptions");
    expect(registry.requests.has(REQUEST_ID)).toBe(true);

    // resolve
    registry.resolve(REQUEST_ID, "response");
    await expect(promise).resolves.toBe(requestId("response"));
  });

  it("should handle request failure", async () => {
    makeRequestMock.mockRejectedValue(new Error("request error"));
    const promise = registry.request("requestOptions");
    await expect(promise).rejects.toThrow("request error");
  });
});
