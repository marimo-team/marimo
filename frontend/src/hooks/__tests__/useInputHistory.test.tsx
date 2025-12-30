/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useInputHistory } from "../useInputHistory";

describe("useInputHistory", () => {
  it("should initialize with empty history", () => {
    const setValue = vi.fn();
    const { result } = renderHook(() =>
      useInputHistory({ value: "", setValue }),
    );
    expect(result.current.history).toEqual([]);
  });

  it("should add command to history", () => {
    const setValue = vi.fn();
    const { result } = renderHook(() =>
      useInputHistory({ value: "", setValue }),
    );

    act(() => {
      result.current.addToHistory("test command");
    });

    expect(result.current.history).toEqual(["test command"]);
  });

  it("should not add duplicate consecutive commands", () => {
    const setValue = vi.fn();
    const { result } = renderHook(() =>
      useInputHistory({ value: "", setValue }),
    );

    act(() => {
      result.current.addToHistory("test");
      result.current.addToHistory("test");
      result.current.addToHistory("test");
    });

    expect(result.current.history).toEqual(["test"]);
  });

  it("should allow same command after different command", () => {
    const setValue = vi.fn();
    const { result } = renderHook(() =>
      useInputHistory({ value: "", setValue }),
    );

    act(() => {
      result.current.addToHistory("first");
      result.current.addToHistory("second");
      result.current.addToHistory("first");
    });

    expect(result.current.history).toEqual(["first", "second", "first"]);
  });

  it("should navigate up through history", () => {
    const setValue = vi.fn();
    const { result, rerender } = renderHook(
      ({ value }) => useInputHistory({ value, setValue }),
      { initialProps: { value: "" } },
    );

    act(() => {
      result.current.addToHistory("first");
      result.current.addToHistory("second");
      result.current.addToHistory("third");
    });

    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).toHaveBeenLastCalledWith("third");

    // Update the value prop to simulate state change
    rerender({ value: "third" });

    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).toHaveBeenLastCalledWith("second");
  });

  it("should navigate down through history", () => {
    const setValue = vi.fn();
    const { result, rerender } = renderHook(
      ({ value }) => useInputHistory({ value, setValue }),
      { initialProps: { value: "" } },
    );

    act(() => {
      result.current.addToHistory("first");
      result.current.addToHistory("second");
    });

    // Navigate up twice
    act(() => {
      result.current.navigateUp();
    });
    rerender({ value: "second" });

    act(() => {
      result.current.navigateUp();
    });
    rerender({ value: "first" });

    // Now navigate down
    act(() => {
      result.current.navigateDown();
    });

    expect(setValue).toHaveBeenLastCalledWith("second");
  });

  it("should preserve pending input when navigating", () => {
    const setValue = vi.fn();
    const { result } = renderHook(
      ({ value }) => useInputHistory({ value, setValue }),
      { initialProps: { value: "pending input" } },
    );

    act(() => {
      result.current.addToHistory("previous command");
    });

    // Navigate up
    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).toHaveBeenLastCalledWith("previous command");

    // Navigate down should restore pending input
    act(() => {
      result.current.navigateDown();
    });

    expect(setValue).toHaveBeenLastCalledWith("pending input");
  });

  it("should not navigate when history is empty", () => {
    const setValue = vi.fn();
    const { result } = renderHook(() =>
      useInputHistory({ value: "current", setValue }),
    );

    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).not.toHaveBeenCalled();

    act(() => {
      result.current.navigateDown();
    });

    expect(setValue).not.toHaveBeenCalled();
  });

  it("should not navigate past the oldest command", () => {
    const setValue = vi.fn();
    const { result, rerender } = renderHook(
      ({ value }) => useInputHistory({ value, setValue }),
      { initialProps: { value: "" } },
    );

    act(() => {
      result.current.addToHistory("only command");
    });

    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).toHaveBeenCalledTimes(1);
    expect(setValue).toHaveBeenLastCalledWith("only command");

    rerender({ value: "only command" });

    // Try to navigate up again - should not change
    act(() => {
      result.current.navigateUp();
    });

    // setValue should not be called again
    expect(setValue).toHaveBeenCalledTimes(1);
  });

  it("should reset navigation state after adding to history", () => {
    const setValue = vi.fn();
    const { result, rerender } = renderHook(
      ({ value }) => useInputHistory({ value, setValue }),
      { initialProps: { value: "" } },
    );

    act(() => {
      result.current.addToHistory("first");
      result.current.addToHistory("second");
    });

    // Navigate up
    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).toHaveBeenLastCalledWith("second");
    rerender({ value: "second" });

    // Add a new command
    act(() => {
      result.current.addToHistory("third");
    });

    // Navigate up should now show 'third'
    act(() => {
      result.current.navigateUp();
    });

    expect(setValue).toHaveBeenLastCalledWith("third");
  });
});
