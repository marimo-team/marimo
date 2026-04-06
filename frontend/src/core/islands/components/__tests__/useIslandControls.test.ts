/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useIslandControls } from "../useIslandControls";

describe("useIslandControls", () => {
  beforeEach(() => {
    // Clean up any event listeners
    document.body.innerHTML = "";
  });

  afterEach(() => {
    // Clean up
    document.body.innerHTML = "";
  });

  it("should return false initially when alwaysShowRun is false", () => {
    const { result } = renderHook(() => useIslandControls(false));
    expect(result.current).toBe(false);
  });

  it("should return true initially when alwaysShowRun is true", () => {
    const { result } = renderHook(() => useIslandControls(true));
    expect(result.current).toBe(true);
  });

  it("should return true when Cmd key is pressed (macOS)", () => {
    const { result } = renderHook(() => useIslandControls(false));

    expect(result.current).toBe(false);

    act(() => {
      const event = new KeyboardEvent("keydown", { metaKey: true });
      document.dispatchEvent(event);
    });

    expect(result.current).toBe(true);
  });

  it("should return true when Ctrl key is pressed (Windows/Linux)", () => {
    const { result } = renderHook(() => useIslandControls(false));

    expect(result.current).toBe(false);

    act(() => {
      const event = new KeyboardEvent("keydown", { ctrlKey: true });
      document.dispatchEvent(event);
    });

    expect(result.current).toBe(true);
  });

  it("should return false when Cmd key is released", () => {
    const { result } = renderHook(() => useIslandControls(false));

    // Press Cmd
    act(() => {
      const event = new KeyboardEvent("keydown", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Release Cmd
    act(() => {
      const event = new KeyboardEvent("keyup", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(false);
  });

  it("should return false when Ctrl key is released", () => {
    const { result } = renderHook(() => useIslandControls(false));

    // Press Ctrl
    act(() => {
      const event = new KeyboardEvent("keydown", { ctrlKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Release Ctrl
    act(() => {
      const event = new KeyboardEvent("keyup", { ctrlKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(false);
  });

  it("should return false when Meta key name is released", () => {
    const { result } = renderHook(() => useIslandControls(false));

    // Press Cmd
    act(() => {
      const event = new KeyboardEvent("keydown", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Release by key name
    act(() => {
      const event = new KeyboardEvent("keyup", { key: "Meta" });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(false);
  });

  it("should return false when Control key name is released", () => {
    const { result } = renderHook(() => useIslandControls(false));

    // Press Ctrl
    act(() => {
      const event = new KeyboardEvent("keydown", { ctrlKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Release by key name
    act(() => {
      const event = new KeyboardEvent("keyup", { key: "Control" });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(false);
  });

  it("should return false when window loses focus", () => {
    const { result } = renderHook(() => useIslandControls(false));

    // Press Cmd
    act(() => {
      const event = new KeyboardEvent("keydown", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Blur window
    act(() => {
      const event = new Event("blur");
      window.dispatchEvent(event);
    });
    expect(result.current).toBe(false);
  });

  it("should return false when mouse leaves window", () => {
    const { result } = renderHook(() => useIslandControls(false));

    // Press Cmd
    act(() => {
      const event = new KeyboardEvent("keydown", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Mouse leave
    act(() => {
      const event = new Event("mouseleave");
      window.dispatchEvent(event);
    });
    expect(result.current).toBe(false);
  });

  it("should not register keyboard event listeners when alwaysShowRun is true", () => {
    const { result } = renderHook(() => useIslandControls(true));

    expect(result.current).toBe(true);

    // Try to change state with keyboard events - should have no effect
    act(() => {
      const event = new KeyboardEvent("keydown", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    act(() => {
      const event = new KeyboardEvent("keyup", { metaKey: true });
      document.dispatchEvent(event);
    });
    expect(result.current).toBe(true);

    // Note: blur and mouseleave listeners are still active and will set pressed to false
    // This is correct behavior to reset state when focus is lost
  });

  it("should handle rapid key presses correctly", () => {
    const { result } = renderHook(() => useIslandControls(false));

    expect(result.current).toBe(false);

    // Multiple rapid presses
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { metaKey: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { metaKey: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { metaKey: true }));
    });
    expect(result.current).toBe(true);

    // Multiple rapid releases
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keyup", { metaKey: true }));
      document.dispatchEvent(new KeyboardEvent("keyup", { metaKey: true }));
      document.dispatchEvent(new KeyboardEvent("keyup", { metaKey: true }));
    });
    expect(result.current).toBe(false);
  });
});
