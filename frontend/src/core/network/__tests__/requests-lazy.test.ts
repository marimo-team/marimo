/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RuntimeManager } from "../../runtime/runtime";
import { createLazyRequests } from "../requests-lazy";
import type { EditRequests, RunRequests } from "../types";

// Mock the connection module
vi.mock("../connection", async () => {
  const { atom } = await import("jotai");
  return {
    connectionAtom: atom({ state: "NOT_STARTED" }),
    waitForConnectionOpen: vi.fn().mockResolvedValue(undefined),
  };
});

// Mock the kernel state module
vi.mock("../../kernel/state", () => ({
  waitForKernelToBeInstantiated: vi.fn().mockResolvedValue(undefined),
}));

describe("createLazyRequests", () => {
  let mockDelegate: EditRequests & RunRequests;
  let mockRuntimeManager: RuntimeManager;
  let mockGetRuntimeManager: () => RuntimeManager;
  let mockInit: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock init function
    mockInit = vi.fn().mockResolvedValue(undefined);

    // Mock runtime manager
    mockRuntimeManager = {
      init: mockInit,
      isLazy: true,
    } as unknown as RuntimeManager;

    // Mock getter function
    mockGetRuntimeManager = vi.fn(() => mockRuntimeManager);

    // Mock delegate with some sample methods
    mockDelegate = {
      sendRun: vi.fn().mockResolvedValue({ success: true }),
      sendInstantiate: vi.fn().mockResolvedValue({ instantiated: true }),
      sendFunctionRequest: vi.fn().mockResolvedValue({ result: "data" }),
      sendRestart: vi.fn().mockResolvedValue({ restarted: true }),
      sendDeleteCell: vi.fn().mockResolvedValue({ deleted: true }),
      sendInterrupt: vi.fn().mockResolvedValue({ interrupted: true }),
      sendPdb: vi.fn().mockResolvedValue({ pdb: true }),
      sendRunScratchpad: vi.fn().mockResolvedValue({ run: true }),
    } as unknown as EditRequests & RunRequests;
  });

  it("should call init once before first request", async () => {
    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    await lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] });

    expect(mockInit).toHaveBeenCalledTimes(1);
  });

  it("should only call init once across multiple requests", async () => {
    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    await lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] });
    await lazyRequests.sendInstantiate({ objectIds: ["obj1"], values: [] });
    await lazyRequests.sendFunctionRequest({
      functionCallId: "func1",
      functionName: "testFunc",
      args: {},
      namespace: "test",
    });

    expect(mockInit).toHaveBeenCalledTimes(1);
  });

  it("should wait for connection before calling delegate method", async () => {
    const { waitForConnectionOpen } = await import("../connection");
    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    await lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] });

    expect(waitForConnectionOpen).toHaveBeenCalled();
  });

  it("should call delegate method with correct arguments", async () => {
    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    const args = { cellIds: ["cell1"], codes: ["code"] };
    await lazyRequests.sendRun(args);

    expect(mockDelegate.sendRun).toHaveBeenCalledWith(args);
  });

  it("should return the result from delegate method", async () => {
    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    const result = await lazyRequests.sendFunctionRequest({
      functionCallId: "func1",
      functionName: "testFunc",
      args: {},
      namespace: "test",
    });

    expect(result).toEqual({ result: "data" });
  });

  it("should wrap all methods from delegate", () => {
    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    expect(lazyRequests.sendRun).toBeDefined();
    expect(lazyRequests.sendInstantiate).toBeDefined();
    expect(lazyRequests.sendFunctionRequest).toBeDefined();
  });

  it("should handle errors from init", async () => {
    const error = new Error("Init failed");
    mockInit.mockRejectedValue(error);

    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    await expect(
      lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] }),
    ).rejects.toThrow("Init failed");
  });

  it("should handle errors from delegate method", async () => {
    const error = new Error("Request failed");
    mockDelegate.sendRun = vi.fn().mockRejectedValue(error);

    const lazyRequests = createLazyRequests(
      mockDelegate,
      mockGetRuntimeManager,
    );

    await expect(
      lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] }),
    ).rejects.toThrow("Request failed");
  });

  describe("Memoization", () => {
    it("should re-initialize if runtime manager changes", async () => {
      const lazyRequests = createLazyRequests(
        mockDelegate,
        mockGetRuntimeManager,
      );

      // First request with first runtime manager
      await lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] });
      expect(mockInit).toHaveBeenCalledTimes(1);

      // Create a new runtime manager
      const mockInit2 = vi.fn().mockResolvedValue(undefined);
      const mockRuntimeManager2 = {
        init: mockInit2,
        isLazy: true,
      } as unknown as RuntimeManager;
      mockGetRuntimeManager = vi.fn(() => mockRuntimeManager2);

      // Create new lazy requests with new getter
      const lazyRequests2 = createLazyRequests(
        mockDelegate,
        mockGetRuntimeManager,
      );

      // Second request with second runtime manager
      await lazyRequests2.sendRun({ cellIds: ["cell2"], codes: ["code2"] });

      // Both inits should have been called
      expect(mockInit).toHaveBeenCalledTimes(1);
      expect(mockInit2).toHaveBeenCalledTimes(1);
    });

    it("should only initialize once per runtime manager instance", async () => {
      const lazyRequests = createLazyRequests(
        mockDelegate,
        mockGetRuntimeManager,
      );

      // Multiple requests
      await lazyRequests.sendRun({ cellIds: ["cell1"], codes: ["code"] });
      await lazyRequests.sendDeleteCell({ cellId: "cell2" });
      await lazyRequests.sendInstantiate({ objectIds: ["obj1"], values: [] });

      // Init should only be called once
      expect(mockInit).toHaveBeenCalledTimes(1);
      expect(mockGetRuntimeManager).toHaveBeenCalledTimes(3);
    });
  });
});
