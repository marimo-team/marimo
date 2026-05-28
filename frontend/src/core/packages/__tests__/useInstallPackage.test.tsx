/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useInstallPackages } from "../useInstallPackage";

const addPackage = vi.fn();
const showAddPackageToast = vi.fn();
let isWasmValue = false;

vi.mock("@/core/wasm/utils", () => ({
  isWasm: () => isWasmValue,
}));

vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ addPackage }),
}));

vi.mock("../toast-components", () => ({
  showAddPackageToast: (...args: unknown[]) => showAddPackageToast(...args),
}));

describe("useInstallPackages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isWasmValue = false;
  });

  it("does not toast in server mode (overlay handles feedback)", async () => {
    addPackage.mockResolvedValue({ success: false, error: "boom" });
    const onSuccess = vi.fn();
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["httpx"], onSuccess);
    });

    expect(addPackage).toHaveBeenCalledWith({ package: "httpx" });
    expect(showAddPackageToast).not.toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });

  it("toasts the error in WASM mode", async () => {
    isWasmValue = true;
    addPackage.mockResolvedValue({ success: false, error: "boom" });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["httpx"]);
    });

    expect(showAddPackageToast).toHaveBeenCalledWith("httpx", "boom");
  });

  it("toasts success (no error) in WASM mode", async () => {
    isWasmValue = true;
    addPackage.mockResolvedValue({ success: true, error: null });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["httpx"]);
    });

    expect(showAddPackageToast).toHaveBeenCalledWith("httpx", undefined);
  });
});
