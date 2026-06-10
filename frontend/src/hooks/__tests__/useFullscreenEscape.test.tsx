/* Copyright 2026 Marimo. All rights reserved. */
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useFullscreenEscape } from "../useFullscreenEscape";

function setFullscreenElement(element: Element | null) {
  Object.defineProperty(document, "fullscreenElement", {
    configurable: true,
    get: () => element,
  });
}

function dispatchEscape(init: KeyboardEventInit = {}) {
  const event = new KeyboardEvent("keydown", {
    key: "Escape",
    cancelable: true,
    ...init,
  });
  window.dispatchEvent(event);
  return event;
}

describe("useFullscreenEscape", () => {
  let element: HTMLElement;
  let exitFullscreen: ReturnType<typeof vi.fn>;
  let lock: ReturnType<typeof vi.fn>;
  let unlock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    element = document.createElement("div");
    document.body.append(element);

    exitFullscreen = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: exitFullscreen,
    });

    lock = vi.fn().mockResolvedValue(undefined);
    unlock = vi.fn();
    Object.defineProperty(navigator, "keyboard", {
      configurable: true,
      value: { lock, unlock },
    });

    setFullscreenElement(null);
  });

  afterEach(() => {
    element.remove();
    vi.restoreAllMocks();
  });

  it("does nothing when disabled", () => {
    const onEscape = vi.fn();
    renderHook(() =>
      useFullscreenEscape({
        enabled: false,
        getElement: () => element,
        onEscape,
      }),
    );
    setFullscreenElement(element);

    dispatchEscape();

    expect(onEscape).not.toHaveBeenCalled();
    expect(exitFullscreen).not.toHaveBeenCalled();
  });

  it("ignores Escape when the owned element is not fullscreen", () => {
    const onEscape = vi.fn(() => false);
    renderHook(() =>
      useFullscreenEscape({ getElement: () => element, onEscape }),
    );

    dispatchEscape();

    expect(onEscape).not.toHaveBeenCalled();
    expect(exitFullscreen).not.toHaveBeenCalled();
  });

  it("ignores non-Escape keys and key repeats", () => {
    const onEscape = vi.fn(() => false);
    renderHook(() =>
      useFullscreenEscape({ getElement: () => element, onEscape }),
    );
    setFullscreenElement(element);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    dispatchEscape({ repeat: true });

    expect(onEscape).not.toHaveBeenCalled();
    expect(exitFullscreen).not.toHaveBeenCalled();
  });

  it("exits fullscreen when onEscape declines", () => {
    const onEscape = vi.fn(() => false);
    renderHook(() =>
      useFullscreenEscape({ getElement: () => element, onEscape }),
    );
    setFullscreenElement(element);

    const event = dispatchEscape();

    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
    expect(event.defaultPrevented).toBe(true);
  });

  it("keeps fullscreen when onEscape handles the key", () => {
    const onEscape = vi.fn(() => true);
    renderHook(() =>
      useFullscreenEscape({ getElement: () => element, onEscape }),
    );
    setFullscreenElement(element);

    const event = dispatchEscape();

    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(exitFullscreen).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("intercepts Escape when a descendant is the fullscreen element", () => {
    const child = document.createElement("div");
    element.append(child);
    const onEscape = vi.fn(() => false);
    renderHook(() =>
      useFullscreenEscape({ getElement: () => element, onEscape }),
    );
    setFullscreenElement(child);

    dispatchEscape();

    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
  });

  it("ignores Escape when an unrelated ancestor is fullscreen", () => {
    const ancestor = document.createElement("div");
    ancestor.append(element);
    document.body.append(ancestor);
    const onEscape = vi.fn(() => false);
    renderHook(() =>
      useFullscreenEscape({ getElement: () => element, onEscape }),
    );
    setFullscreenElement(ancestor);

    dispatchEscape();

    expect(onEscape).not.toHaveBeenCalled();
    expect(exitFullscreen).not.toHaveBeenCalled();
  });

  it("locks Escape when mounted already in fullscreen", () => {
    setFullscreenElement(element);

    renderHook(() => useFullscreenEscape({ getElement: () => element }));

    expect(lock).toHaveBeenCalledWith(["Escape"]);
  });

  it("locks Escape on entering fullscreen and unlocks on leaving", () => {
    renderHook(() => useFullscreenEscape({ getElement: () => element }));

    setFullscreenElement(element);
    document.dispatchEvent(new Event("fullscreenchange"));
    expect(lock).toHaveBeenCalledWith(["Escape"]);

    setFullscreenElement(null);
    document.dispatchEvent(new Event("fullscreenchange"));
    expect(unlock).toHaveBeenCalled();
  });

  it("unlocks Escape on unmount when it holds the lock", () => {
    setFullscreenElement(element);
    const { unmount } = renderHook(() =>
      useFullscreenEscape({ getElement: () => element }),
    );
    expect(lock).toHaveBeenCalledWith(["Escape"]);

    unmount();

    expect(unlock).toHaveBeenCalledTimes(1);
  });

  it("never unlocks a lock it did not acquire", () => {
    // Not fullscreen, so this instance never locks. Mount, a stray
    // fullscreenchange, and unmount must not release another component's lock.
    const { unmount } = renderHook(() =>
      useFullscreenEscape({ getElement: () => element }),
    );
    document.dispatchEvent(new Event("fullscreenchange"));
    unmount();

    expect(unlock).not.toHaveBeenCalled();
  });
});
