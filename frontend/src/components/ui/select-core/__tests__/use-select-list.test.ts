/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { BulkAction, Option } from "../types";
import { useSelectList } from "../use-select-list";

const opts: Array<Option<string>> = [
  { value: "a", label: "apple" },
  { value: "b", label: "banana" },
  { value: "c", label: "cherry" },
];

describe("useSelectList - search", () => {
  it("filters visibleOptions by label using the strict word match", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: [],
        onChange: vi.fn(),
        multiple: true,
      }),
    );
    act(() => result.current.setSearchQuery("ban"));
    expect(result.current.visibleOptions.map((o) => o.value)).toEqual(["b"]);
  });

  it("returns all options when the query is empty", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: [],
        onChange: vi.fn(),
        multiple: true,
      }),
    );
    expect(result.current.visibleOptions).toHaveLength(3);
  });

  it("keeps options for any positive filter score, not just 1", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: [],
        onChange: vi.fn(),
        multiple: true,
        filterFn: (label) => (label === "apple" ? 0.5 : 0),
      }),
    );
    act(() => result.current.setSearchQuery("anything"));
    expect(result.current.visibleOptions.map((o) => o.value)).toEqual(["a"]);
  });
});

describe("useSelectList - multi toggle", () => {
  it("adds an unselected value", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({ options: opts, value: ["a"], onChange, multiple: true }),
    );
    act(() => result.current.toggle("b"));
    expect(onChange).toHaveBeenCalledWith(["a", "b"]);
  });

  it("removes a selected value", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: ["a", "b"],
        onChange,
        multiple: true,
      }),
    );
    act(() => result.current.toggle("a"));
    expect(onChange).toHaveBeenCalledWith(["b"]);
  });

  it("drops the oldest selection when maxSelections is exceeded", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: ["a", "b"],
        onChange,
        multiple: true,
        maxSelections: 2,
      }),
    );
    act(() => result.current.toggle("c"));
    expect(onChange).toHaveBeenCalledWith(["b", "c"]);
  });

  it("isChecked reflects membership", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: ["a"],
        onChange: vi.fn(),
        multiple: true,
      }),
    );
    expect(result.current.isChecked("a")).toBe(true);
    expect(result.current.isChecked("b")).toBe(false);
  });
});

describe("useSelectList - single toggle", () => {
  it("replaces the value", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({ options: opts, value: "a", onChange, multiple: false }),
    );
    act(() => result.current.toggle("b"));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("clears to null when allowSelectNone and the value is re-toggled", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: "a",
        onChange,
        multiple: false,
        allowSelectNone: true,
      }),
    );
    act(() => result.current.toggle("a"));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});

describe("useSelectList - pinning + freeze", () => {
  it("pins selected to the top of visibleOptions when open and idle", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: ["c"],
        onChange: vi.fn(),
        multiple: true,
        pinSelected: true,
      }),
    );
    act(() => result.current.setOpen(true));
    expect(result.current.visibleOptions.map((o) => o.value)).toEqual([
      "c",
      "a",
      "b",
    ]);
    expect(result.current.pinnedCount).toBe(1);
  });

  it("freezes pinned order while open: a newly toggled item does not re-pin", () => {
    const onChange = vi.fn();
    const { result, rerender } = renderHook(
      ({ value }) =>
        useSelectList({
          options: opts,
          value,
          onChange,
          multiple: true,
          pinSelected: true,
        }),
      { initialProps: { value: ["c"] as string[] } },
    );
    act(() => result.current.setOpen(true));
    rerender({ value: ["c", "a"] });
    expect(result.current.visibleOptions.map((o) => o.value)).toEqual([
      "c",
      "a",
      "b",
    ]);
    expect(result.current.isChecked("a")).toBe(true);
  });

  it("re-pins when the search clears", () => {
    const { result, rerender } = renderHook(
      ({ value }) =>
        useSelectList({
          options: opts,
          value,
          onChange: vi.fn(),
          multiple: true,
          pinSelected: true,
        }),
      { initialProps: { value: ["b"] as string[] } },
    );
    act(() => result.current.setOpen(true));
    act(() => result.current.setSearchQuery("a"));
    rerender({ value: ["b", "a"] });
    act(() => result.current.setSearchQuery(""));
    expect(result.current.visibleOptions.map((o) => o.value)).toEqual([
      "b",
      "a",
      "c",
    ]);
  });

  it("does not pin when pinSelected is false", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: ["c"],
        onChange: vi.fn(),
        multiple: true,
      }),
    );
    act(() => result.current.setOpen(true));
    expect(result.current.visibleOptions.map((o) => o.value)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(result.current.pinnedCount).toBe(0);
  });
});

describe("useSelectList - bulk", () => {
  const findAction = <K extends BulkAction<string>["kind"]>(
    actions: ReadonlyArray<BulkAction<string>>,
    kind: K,
  ): Extract<BulkAction<string>, { kind: K }> | undefined =>
    actions.find(
      (a): a is Extract<BulkAction<string>, { kind: K }> => a.kind === kind,
    );

  it("idle: select-all picks every option; deselect-all clears", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({ options: opts, value: ["a"], onChange, multiple: true }),
    );
    act(() => findAction(result.current.bulkActions, "select-all")?.run());
    expect(onChange).toHaveBeenCalledWith(["a", "b", "c"]);
    onChange.mockClear();
    act(() => findAction(result.current.bulkActions, "deselect-all")?.run());
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("idle: select-all skips disabled options and keeps the existing selection", () => {
    const onChange = vi.fn();
    const withDisabled: Array<Option<string>> = [
      { value: "a", label: "apple" },
      { value: "b", label: "banana", disabled: true },
      { value: "c", label: "cherry" },
    ];
    const { result } = renderHook(() =>
      useSelectList({
        options: withDisabled,
        value: ["c"],
        onChange,
        multiple: true,
      }),
    );
    act(() => findAction(result.current.bulkActions, "select-all")?.run());
    expect(onChange).toHaveBeenCalledWith(["c", "a"]);
  });

  it("searching: select-matching acts only on the matches (additive)", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useSelectList({ options: opts, value: ["a"], onChange, multiple: true }),
    );
    act(() => result.current.setSearchQuery("b"));
    act(() => findAction(result.current.bulkActions, "select-matching")?.run());
    expect(onChange).toHaveBeenCalledWith(["a", "b"]);
  });

  it("exposes idle bulkActions in select-then-deselect order", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: ["a"],
        onChange: vi.fn(),
        multiple: true,
      }),
    );
    const kinds = result.current.bulkActions.map((a) => a.kind);
    expect(kinds).toEqual(["select-all", "deselect-all"]);
    const selectAll = findAction(result.current.bulkActions, "select-all");
    expect(selectAll && "enabled" in selectAll && selectAll.enabled).toBe(true);
  });

  it("bulkActions is empty for single-select", () => {
    const { result } = renderHook(() =>
      useSelectList({
        options: opts,
        value: "a",
        onChange: vi.fn(),
        multiple: false,
      }),
    );
    expect(result.current.bulkActions).toEqual([]);
  });
});
