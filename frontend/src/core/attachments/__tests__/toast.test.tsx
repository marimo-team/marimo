/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, render, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/toaster";
import { clearToasts, toast, useToast } from "@/components/ui/use-toast";
import { agentToast } from "../toast";

describe("agent notifications", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearToasts();
  });

  afterEach(() => {
    act(() => {
      clearToasts();
      vi.runOnlyPendingTimers();
    });
    vi.useRealTimers();
  });

  it.each([
    { variant: undefined, duration: 3000 },
    { variant: "danger" as const, duration: 5000 },
  ])("expires while the window is blurred: %j", ({ variant, duration }) => {
    const { result } = renderHook(useToast);
    render(<Toaster />);
    act(() => agentToast({ title: "Agent notice", variant }));
    act(() => window.dispatchEvent(new Event("blur")));
    act(() => vi.advanceTimersByTime(duration - 1));
    expect(result.current.toasts[0].open).toBe(true);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.toasts[0].open).toBe(false);
  });

  it("preserves pause behavior for ordinary notifications", () => {
    const { result } = renderHook(useToast);
    render(<Toaster />);
    act(() => toast({ title: "Ordinary notice", duration: 3000 }));
    act(() => window.dispatchEvent(new Event("blur")));
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.toasts[0].open).toBe(true);
  });

  it("does not let an older timer dismiss a newer notification", () => {
    const { result } = renderHook(useToast);
    act(() => agentToast({ title: "First" }));
    act(() => vi.advanceTimersByTime(1000));
    act(() => agentToast({ title: "Second" }));
    act(() => vi.advanceTimersByTime(2000));
    expect(result.current.toasts[0].title).toBe("Second");
    expect(result.current.toasts[0].open).toBe(true);
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.toasts[0].open).toBe(false);
  });
});
