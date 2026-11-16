/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  render as renderComponent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Provider, createStore } from "jotai";
import type { ReactNode } from "react";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import { DynamicFavicon } from "../dynamic-favicon";

describe("DynamicFavicon", () => {
  let favicon: HTMLLinkElement;
  let store: ReturnType<typeof createStore>;
  const id = cellId("cell");

  function render(ui: ReactNode) {
    return renderComponent(ui, {
      wrapper: ({ children }) => <Provider store={store}>{children}</Provider>,
    });
  }

  function setErrors() {
    store.set(
      notebookAtom,
      MockNotebook.notebookStateWithErrors([
        {
          cellId: id,
          cellName: "cell",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
      ]),
    );
  }

  beforeEach(() => {
    document
      .querySelectorAll("link[rel~='icon']")
      .forEach((element) => element.remove());

    // Mock favicon element
    favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.href = "./favicon.ico";
    document.head.append(favicon);

    // Mock document.hasFocus
    vi.spyOn(document, "hasFocus").mockReturnValue(true);

    store = createStore();
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [id]: { code: "x = 1" } },
      }),
    );
  });

  afterEach(() => {
    document
      .querySelectorAll("link[rel~='icon']")
      .forEach((element) => element.remove());
    vi.restoreAllMocks();
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
    setErrors();

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

  it("recreates a removed favicon when the window regains focus", async () => {
    render(<DynamicFavicon isRunning={false} />);
    favicon.remove();

    window.dispatchEvent(new Event("focus"));

    await waitFor(() => {
      const currentFavicon =
        document.querySelector<HTMLLinkElement>("link[rel~='icon']");
      expect(currentFavicon?.href.endsWith("favicon.ico")).toBe(true);
    });
  });

  it("resets the current favicon after the link is replaced", async () => {
    render(<DynamicFavicon isRunning={false} />);
    const replacement = document.createElement("link");
    replacement.rel = "icon";
    replacement.href = "./replacement.ico";
    favicon.replaceWith(replacement);

    window.dispatchEvent(new Event("focus"));

    await waitFor(() => {
      expect(replacement.href.endsWith("favicon.ico")).toBe(true);
      expect(document.querySelector("link[rel~='icon']")).toBe(replacement);
    });
  });

  it("does not look up or rewrite the favicon when code changes", async () => {
    const { rerender } = render(<DynamicFavicon isRunning={true} />);
    await waitFor(() => expect(favicon.href).toContain("circle-play.ico"));
    rerender(<DynamicFavicon isRunning={false} />);
    await waitFor(() => expect(favicon.href).toContain("circle-check.ico"));
    const lookup = vi.spyOn(document, "querySelector");
    const write = vi.spyOn(favicon, "href", "set");

    await act(async () => {
      store.set(notebookAtom, (state) => ({
        ...state,
        cellData: {
          ...state.cellData,
          [id]: { ...state.cellData[id], code: "x = 2" },
        },
      }));
    });

    expect(
      lookup.mock.calls.filter(
        ([selector]) => selector === "link[rel~='icon']",
      ),
    ).toEqual([]);
    expect(write).not.toHaveBeenCalled();
    lookup.mockRestore();
    write.mockRestore();
  });

  it("updates the favicon when the error count changes", async () => {
    const { rerender } = render(<DynamicFavicon isRunning={true} />);
    await waitFor(() => expect(favicon.href).toContain("circle-play.ico"));
    rerender(<DynamicFavicon isRunning={false} />);
    await waitFor(() => expect(favicon.href).toContain("circle-check.ico"));

    act(() => setErrors());
    await waitFor(() => expect(favicon.href).toContain("circle-x.ico"));

    act(() =>
      store.set(
        notebookAtom,
        MockNotebook.notebookState({ cellData: { [id]: {} } }),
      ),
    );
    await waitFor(() => expect(favicon.href).toContain("circle-check.ico"));
  });

  it("keeps the completion icon until its own reset timer expires", async () => {
    vi.useFakeTimers();
    const { rerender } = render(<DynamicFavicon isRunning={true} />);
    await act(() => vi.advanceTimersByTimeAsync(1000));
    rerender(<DynamicFavicon isRunning={false} />);
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(favicon.href).toContain("circle-check.ico");
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(favicon.href).toContain("favicon.ico");
  });

  it("cancels the reset timer when unmounted", async () => {
    vi.useFakeTimers();
    const { unmount } = render(<DynamicFavicon isRunning={true} />);
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  describe("notifications", () => {
    beforeEach(() => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
      // @ts-expect-error ok in tests
      global.Notification = vi.fn();
      // @ts-expect-error ok in tests
      global.Notification.permission = "granted";
    });

    it("should send success notification when run completes without errors", async () => {
      // @ts-expect-error ok in tests
      global.Notification = vi
        .fn()
        .mockImplementation(function (title, options) {
          expect(title).toBe("Execution completed");
          expect(options).toEqual({
            body: "Your notebook run completed successfully.",
            icon: "/src/assets/circle-check.ico",
          });
        });
      // @ts-expect-error ok in tests
      global.Notification.permission = "granted";

      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);
      await waitFor(() => expect(Notification).toHaveBeenCalledOnce());
    });

    it("should send error notification when run completes with errors", async () => {
      setErrors();

      // @ts-expect-error ok in tests
      global.Notification = vi
        .fn()
        .mockImplementation(function (title, options) {
          expect(title).toBe("Execution failed");
          expect(options).toEqual({
            body: "Your notebook run encountered 1 error(s).",
            icon: "/src/assets/circle-x.ico",
          });
        });
      // @ts-expect-error ok in tests
      global.Notification.permission = "granted";

      const { rerender } = render(<DynamicFavicon isRunning={true} />);
      rerender(<DynamicFavicon isRunning={false} />);
      await waitFor(() => expect(Notification).toHaveBeenCalledOnce());
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

      // oxlint-disable-next-line typescript/unbound-method
      expect(Notification.requestPermission).toHaveBeenCalled();
    });
  });
});
