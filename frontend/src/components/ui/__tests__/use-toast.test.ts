/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast, useToast } from "@/components/ui/use-toast";

describe("toast once", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.dismiss();
      vi.runAllTimers();
    });
    vi.useRealTimers();
  });

  it("shows a once-toast a single time per session, even after removal", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      toast({ id: "static-notebook", once: true, title: "Static notebook" });
    });
    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      result.current.dismiss("static-notebook");
      vi.advanceTimersByTime(10_000);
    });
    expect(result.current.toasts).toHaveLength(0);

    act(() => {
      toast({ id: "static-notebook", once: true, title: "Static notebook" });
    });
    expect(result.current.toasts).toHaveLength(0);
  });

  it("does not suppress normal (non-once) toasts", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      toast({ id: "normal", title: "First" });
    });
    act(() => {
      result.current.dismiss("normal");
      vi.advanceTimersByTime(10_000);
    });
    expect(result.current.toasts).toHaveLength(0);

    act(() => {
      toast({ id: "normal", title: "First" });
    });
    expect(result.current.toasts).toHaveLength(1);
  });

  it("does not dedupe a once-toast without a stable id", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      toast({ once: true, title: "No id" });
    });
    act(() => {
      result.current.dismiss();
      vi.advanceTimersByTime(10_000);
    });
    expect(result.current.toasts).toHaveLength(0);

    act(() => {
      toast({ once: true, title: "No id" });
    });
    expect(result.current.toasts).toHaveLength(1);
  });
});
