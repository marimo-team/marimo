/* Copyright 2026 Marimo. All rights reserved. */
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useInstallPackages } from "../useInstallPackage";
import { Toast, ToastProvider, ToastViewport } from "@/components/ui/toast";

const toast = vi.fn();
const addPackage = vi.fn();
const restartKernel = vi.fn();

vi.mock("@/components/editor/actions/useRestartKernel", () => ({
  useRestartKernel: () => restartKernel,
}));

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
    restartKernel.mockClear();
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

  it("reports saved changes requiring restart without claiming installation", async () => {
    addPackage.mockResolvedValue({
      success: false,
      error: null,
      restartRequired: true,
    });
    const { result } = renderHook(() => useInstallPackages());
    await act(async () => {
      await result.current.handleInstallPackages(["boltons", "six"]);
    });
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Changes saved — restart required",
        description: expect.stringContaining(
          "Restarting clears in-memory variables",
        ),
        duration: Infinity,
        action: expect.anything(),
      }),
    );
    expect(toast.mock.calls[0][0].variant).not.toBe("danger");
    render(
      <ToastProvider>
        <Toast>{toast.mock.calls[0][0].action}</Toast>
        <ToastViewport />
      </ToastProvider>,
    );
    expect(restartKernel).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Restart Kernel" }));
    expect(restartKernel).toHaveBeenCalledTimes(1);
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
