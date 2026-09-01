/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useInstallPackages } from "../useInstallPackage";

const toast = vi.fn();
const addPackage = vi.fn();

vi.mock("@/components/ui/use-toast", () => ({
  toast: (...args: unknown[]) => toast(...args),
}));

vi.mock("../../network/requests", () => ({
  useRequestClient: () => ({
    addPackage: (...args: unknown[]) => addPackage(...args),
  }),
}));

describe("useInstallPackages", () => {
  beforeEach(() => {
    toast.mockClear();
    addPackage.mockClear();
  });

  it("batches all packages into a single install call", async () => {
    addPackage.mockResolvedValue({ success: true, error: null });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["numpy", "pandas", "scipy"]);
    });

    // A single batched install call, not one per package.
    expect(addPackage).toHaveBeenCalledTimes(1);
    expect(addPackage).toHaveBeenCalledWith({ package: "numpy pandas scipy" });
  });

  it("shows a single aggregate success toast for multiple packages", async () => {
    addPackage.mockResolvedValue({ success: true, error: null });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["numpy", "pandas", "scipy"]);
    });

    // Only one toast, regardless of package count — no false per-package status.
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Packages added" }),
    );
  });

  it("shows a single aggregate error toast when the batch fails", async () => {
    addPackage.mockResolvedValue({ success: false, error: "boom" });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["numpy", "pandas"]);
    });

    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Failed to add packages",
        description: "boom",
        variant: "danger",
      }),
    );
  });

  it("collapses a partial (mixed) failure into one aggregate error toast", async () => {
    // The backend resolves the batch as a single transaction and reports an
    // aggregate outcome, so even when only some packages fail we surface a
    // single error toast covering the whole batch — never a per-package
    // success/failure split the response can't actually represent.
    addPackage.mockResolvedValue({
      success: false,
      error: "pandas failed to install",
    });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["numpy", "pandas"]);
    });

    expect(addPackage).toHaveBeenCalledTimes(1);
    expect(addPackage).toHaveBeenCalledWith({ package: "numpy pandas" });
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Failed to add packages",
        description: "pandas failed to install",
        variant: "danger",
      }),
    );
  });

  it("uses singular wording for a single package", async () => {
    addPackage.mockResolvedValue({ success: true, error: null });
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["numpy"]);
    });

    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Package added" }),
    );
  });

  it("calls onSuccess after a successful install", async () => {
    addPackage.mockResolvedValue({ success: true, error: null });
    const onSuccess = vi.fn();
    const { result } = renderHook(() => useInstallPackages());

    await act(async () => {
      await result.current.handleInstallPackages(["numpy"], onSuccess);
    });

    expect(onSuccess).toHaveBeenCalledTimes(1);
  });
});
