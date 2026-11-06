/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectionState } from "../../session/types";
import { useAutoSave } from "../useAutoSave";

function options(): Parameters<typeof useAutoSave>[0] {
  return {
    version: 1,
    config: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    connStatus: { state: ConnectionState.OPEN },
    needsSave: true,
    canEdit: true,
    onSave: vi.fn(),
  };
}

describe("useAutoSave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("waits for the full delay after the latest confirmed change", () => {
    const initial = options();
    const { rerender } = renderHook(useAutoSave, { initialProps: initial });

    act(() => vi.advanceTimersByTime(600));
    rerender({ ...initial, version: 2 });
    act(() => vi.advanceTimersByTime(999));
    expect(initial.onSave).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(initial.onSave).toHaveBeenCalledExactlyOnceWith();
  });

  it("cancels pending saves when editing is disabled or the component unmounts", () => {
    const initial = options();
    const { rerender, unmount } = renderHook(useAutoSave, {
      initialProps: initial,
    });

    act(() => vi.advanceTimersByTime(600));
    rerender({ ...initial, canEdit: false });
    act(() => vi.advanceTimersByTime(1000));
    expect(initial.onSave).not.toHaveBeenCalled();

    rerender(initial);
    act(() => vi.advanceTimersByTime(999));
    expect(initial.onSave).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(initial.onSave).toHaveBeenCalledExactlyOnceWith();

    rerender({ ...initial, version: 2 });
    unmount();
    act(() => vi.advanceTimersByTime(1000));
    expect(initial.onSave).toHaveBeenCalledExactlyOnceWith();
  });
});
