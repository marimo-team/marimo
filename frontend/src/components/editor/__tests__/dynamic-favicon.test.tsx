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
  let mockFetch: ReturnType<typeof vi.fn>;
  let mockCreateObjectURL: ReturnType<typeof vi.fn>;
  let mockRevokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Mock favicon element
    favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.href = "./favicon.ico";
    document.head.append(favicon);

    // Mock fetch
    mockFetch = vi.fn().mockResolvedValue({
      blob: () => new Blob(),
    });
    global.fetch = mockFetch;

    // Mock URL methods
    mockCreateObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    mockRevokeObjectURL = vi.fn();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

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

    expect(mockFetch).toHaveBeenCalledWith("./circle-play.ico");
  });

  it("should not reset favicon when not in focus", async () => {
    vi.spyOn(document, "hasFocus").mockReturnValue(false);
    vi.useFakeTimers();
    render(<DynamicFavicon isRunning={false} />);
    vi.clearAllMocks();

    await vi.advanceTimersByTimeAsync(3000);

    expect(mockFetch).not.toHaveBeenCalledWith("./favicon.ico");
  });

  it("should create favicon link if none exists", () => {
    favicon.remove();
    render(<DynamicFavicon isRunning={true} />);

    const newFavicon = document.querySelector("link[rel~='icon']");
    expect(newFavicon).not.toBeNull();
  });

  it("should cleanup object URLs on unmount", () => {
    const { unmount } = render(<DynamicFavicon isRunning={true} />);
    unmount();

    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });

  describe("notifications", () => {
    beforeEach(() => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
      // @ts-expect-error ok in tests
      global.Notification = vi.fn();
      // @ts-expect-error ok in tests
      global.Notification.permission = "granted";
    });

    it("should send success notification when run completes without errors", () => {
      // @ts-expect-error ok in tests
      global.Notification = vi.fn().mockImplementation((title, options) => {
        expect(title).toBe("Execution completed");
        expect(options).toEqual({
          body: "Your notebook run completed successfully.",
          icon: expect.any(String),
        });
      });
      // @ts-expect-error ok in tests
      global.Notification.permission = "granted";

      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);
    });

    it("should not send notification when document is visible", () => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);

      expect(Notification).not.toHaveBeenCalled();
    });

    it("should request permission if not granted", () => {
      // @ts-expect-error ok in tests
      global.Notification.permission = "default";
      global.Notification.requestPermission = vi
        .fn()
        .mockResolvedValue("granted");

      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);

      // eslint-disable-next-line @typescript-eslint/unbound-method
      expect(Notification.requestPermission).toHaveBeenCalled();
    });
  });
});
