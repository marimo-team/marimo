/* Copyright 2024 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useCellErrors } from "@/core/cells/cells";
import { DynamicFavicon } from "../dynamic-favicon";

// Mock useCellErrors hook
vi.mock("@/core/cells/cells", () => ({
  useCellErrors: vi.fn(),
}));

describe("DynamicFavicon", () => {
  let favicon: HTMLLinkElement;

  beforeEach(() => {
    // Mock favicon element
    favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.href = "./favicon.ico";
    document.head.append(favicon);

    // Mock document.hasFocus
    vi.spyOn(document, "hasFocus").mockReturnValue(true);

    // Mock useCellErrors to return no errors by default
    (useCellErrors as ReturnType<typeof vi.fn>).mockReturnValue([]);
  });

  afterEach(() => {
    favicon.remove();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("should update favicon when running state changes", async () => {
    render(<DynamicFavicon isRunning={true} />);

    // Wait for async favicon update
    await new Promise((resolve) => setTimeout(resolve, 0));

    const faviconElement =
      document.querySelector<HTMLLinkElement>("link[rel~='icon']")!;
    expect(faviconElement.href.endsWith("circle-play.ico")).toBe(true);
  });

  it("should show success favicon when run completes without errors", async () => {
    const { rerender } = render(<DynamicFavicon isRunning={true} />);

    // Wait for the running favicon to be set
    await new Promise((resolve) => setTimeout(resolve, 0));

    rerender(<DynamicFavicon isRunning={false} />);

    // Wait for async favicon update
    await new Promise((resolve) => setTimeout(resolve, 0));

    const faviconElement =
      document.querySelector<HTMLLinkElement>("link[rel~='icon']")!;
    expect(faviconElement.href.endsWith("circle-check.ico")).toBe(true);
  });

  it("should show error favicon when run completes with errors", async () => {
    (useCellErrors as ReturnType<typeof vi.fn>).mockReturnValue([
      { error: "mock error" },
    ]);

    const { rerender } = render(<DynamicFavicon isRunning={true} />);

    // Wait for the running favicon to be set
    await new Promise((resolve) => setTimeout(resolve, 0));

    rerender(<DynamicFavicon isRunning={false} />);

    // Wait for async favicon update
    await new Promise((resolve) => setTimeout(resolve, 0));

    const faviconElement =
      document.querySelector<HTMLLinkElement>("link[rel~='icon']")!;
    expect(faviconElement.href.endsWith("circle-x.ico")).toBe(true);
  });

  it("should not reset favicon when not in focus", async () => {
    vi.spyOn(document, "hasFocus").mockReturnValue(false);
    vi.useFakeTimers();

    const { rerender } = render(<DynamicFavicon isRunning={true} />);

    // Wait for the running favicon to be set
    await vi.advanceTimersByTimeAsync(0);

    rerender(<DynamicFavicon isRunning={false} />);

    // Wait for async favicon update
    await vi.advanceTimersByTimeAsync(0);

    const faviconElement =
      document.querySelector<HTMLLinkElement>("link[rel~='icon']")!;
    expect(faviconElement.href.endsWith("circle-check.ico")).toBe(true);

    // Advance timers beyond the 3-second reset timeout
    await vi.advanceTimersByTimeAsync(3000);

    // Favicon should still be the success one since document is not in focus
    expect(faviconElement.href.endsWith("circle-check.ico")).toBe(true);
  });

  it("should create favicon link if none exists", () => {
    favicon.remove();
    render(<DynamicFavicon isRunning={true} />);

    const newFavicon = document.querySelector("link[rel~='icon']");
    expect(newFavicon).not.toBeNull();
  });

  describe("notifications", () => {
    let notificationSpy: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
      notificationSpy = vi.fn();
      // Create a class mock that can be called with `new`
      // @ts-expect-error ok in tests
      // eslint-disable-next-line @typescript-eslint/no-extraneous-class
      global.Notification = class MockNotification {
        constructor(title: string, options?: NotificationOptions) {
          notificationSpy(title, options);
        }

        static permission: NotificationPermission = "granted";
        static requestPermission = vi.fn().mockResolvedValue("granted");
      };
    });

    it("should send success notification when run completes without errors", async () => {
      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);

      // Wait for async notification
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(notificationSpy).toHaveBeenCalledWith("Execution completed", {
        body: "Your notebook run completed successfully.",
        icon: "/src/assets/circle-check.ico",
      });
    });

    it("should send error notification when run completes with errors", async () => {
      (useCellErrors as ReturnType<typeof vi.fn>).mockReturnValue([
        { error: "mock error" },
      ]);

      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);

      // Wait for async notification
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(notificationSpy).toHaveBeenCalledWith("Execution failed", {
        body: "Your notebook run encountered 1 error(s).",
        icon: "/src/assets/circle-x.ico",
      });
    });

    it("should not send notification when document is visible", () => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);

      expect(notificationSpy).not.toHaveBeenCalled();
    });

    it("should request permission if not granted", () => {
      // @ts-expect-error ok in tests
      global.Notification.permission = "default";

      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);

      // eslint-disable-next-line @typescript-eslint/unbound-method
      expect(Notification.requestPermission).toHaveBeenCalled();
    });
  });
});
