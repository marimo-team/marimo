/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withLoadingToast } from "../download";

// Mock the toast module
const mockDismiss = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(() => ({
    dismiss: mockDismiss,
  })),
}));

// Mock the Spinner component
vi.mock("@/components/icons/spinner", () => ({
  Spinner: () => "MockSpinner",
}));

import { toast } from "@/components/ui/use-toast";

describe("withLoadingToast", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should show a loading toast and dismiss on success", async () => {
    const result = await withLoadingToast("Loading...", async () => {
      return "success";
    });

    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith({
      title: "Loading...",
    });
    expect(mockDismiss).toHaveBeenCalledTimes(1);
    expect(result).toBe("success");
  });

  it("should dismiss toast and rethrow on error", async () => {
    const error = new Error("Operation failed");

    await expect(
      withLoadingToast("Loading...", async () => {
        throw error;
      }),
    ).rejects.toThrow("Operation failed");

    expect(toast).toHaveBeenCalledTimes(1);
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  it("should return the value from the async function", async () => {
    const expectedValue = { data: "test", count: 42 };

    const result = await withLoadingToast("Processing...", async () => {
      return expectedValue;
    });

    expect(result).toEqual(expectedValue);
  });

  it("should handle void functions", async () => {
    let sideEffect = false;

    await withLoadingToast("Saving...", async () => {
      sideEffect = true;
    });

    expect(sideEffect).toBe(true);
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  it("should use the provided title in the toast", async () => {
    const customTitle = "Downloading PDF...";

    await withLoadingToast(customTitle, async () => "done");

    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: customTitle,
      }),
    );
  });

  it("should wait for the async function to complete", async () => {
    const events: string[] = [];

    await withLoadingToast("Loading...", async () => {
      events.push("start");
      await new Promise((resolve) => setTimeout(resolve, 10));
      events.push("end");
    });

    expect(events).toEqual(["start", "end"]);
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });
});
