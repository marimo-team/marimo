/* Copyright 2026 Marimo. All rights reserved. */
import { renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { Functions } from "@/utils/functions";
import { useHotkey } from "../useHotkey";

// global.hideCode is bound to "Mod-." by default; "mod" accepts ctrl or meta.
const SHORTCUT = "global.hideCode";

function createWrapper() {
  const store = createStore();
  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

function press() {
  const event = new KeyboardEvent("keydown", {
    key: ".",
    ctrlKey: true,
    cancelable: true,
    bubbles: true,
  });
  document.dispatchEvent(event);
  return event;
}

describe("useHotkey", () => {
  it("invokes the callback and prevents default", () => {
    const callback = vi.fn();
    renderHook(() => useHotkey(SHORTCUT, callback), {
      wrapper: createWrapper(),
    });

    const event = press();
    expect(callback).toHaveBeenCalledOnce();
    expect(event.defaultPrevented).toBe(true);
  });

  it("does not prevent default when the callback returns false", () => {
    const callback = vi.fn(() => false);
    renderHook(() => useHotkey(SHORTCUT, callback), {
      wrapper: createWrapper(),
    });

    const event = press();
    expect(callback).toHaveBeenCalledOnce();
    expect(event.defaultPrevented).toBe(false);
  });

  it("still swallows the keystroke for NOOP catch-all handlers", () => {
    renderHook(() => useHotkey(SHORTCUT, Functions.NOOP), {
      wrapper: createWrapper(),
    });

    const event = press();
    expect(event.defaultPrevented).toBe(true);
  });

  it("neither runs the callback nor prevents default when disabled", () => {
    const callback = vi.fn();
    renderHook(() => useHotkey(SHORTCUT, callback, { disabled: true }), {
      wrapper: createWrapper(),
    });

    const event = press();
    expect(callback).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("re-enables when disabled flips back to false", () => {
    const callback = vi.fn();
    const { rerender } = renderHook(
      ({ disabled }: { disabled: boolean }) =>
        useHotkey(SHORTCUT, callback, { disabled }),
      { wrapper: createWrapper(), initialProps: { disabled: true } },
    );

    press();
    expect(callback).not.toHaveBeenCalled();

    rerender({ disabled: false });
    const event = press();
    expect(callback).toHaveBeenCalledOnce();
    expect(event.defaultPrevented).toBe(true);
  });
});
