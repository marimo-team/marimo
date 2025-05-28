/* Copyright 2024 Marimo. All rights reserved. */
import { SELECT_COLUMN_ID } from "../types";
import { renderHook, act } from "@testing-library/react-hooks";
import { describe, it, expect } from "vitest";
import { useColumnPinning } from "../hooks/use-column-pinning";

describe("useColumnPinning", () => {
  it("should initialize with correct default values", () => {
    const { result } = renderHook(() => useColumnPinning());
    expect(result.current.columnPinning).toEqual({
      left: [],
      right: undefined,
    });
  });

  it("should add SELECT_COLUMN_ID to left when freezeColumnsLeft is provided", () => {
    const { result } = renderHook(() =>
      useColumnPinning(["column1", "column2"]),
    );
    expect(result.current.columnPinning.left).toEqual([
      SELECT_COLUMN_ID,
      "column1",
      "column2",
    ]);
  });

  it("should not add SELECT_COLUMN_ID if it's already present", () => {
    const { result } = renderHook(() =>
      useColumnPinning([SELECT_COLUMN_ID, "column1"]),
    );
    expect(result.current.columnPinning.left).toEqual([
      SELECT_COLUMN_ID,
      "column1",
    ]);
  });

  it("should set right columns correctly", () => {
    const { result } = renderHook(() =>
      useColumnPinning(undefined, ["column3", "column4"]),
    );
    expect(result.current.columnPinning.right).toEqual(["column3", "column4"]);
  });

  it("should update column pinning state correctly", () => {
    const { result } = renderHook(() => useColumnPinning());

    act(() => {
      result.current.setColumnPinning({
        left: ["column1"],
        right: ["column2"],
      });
    });

    expect(result.current.columnPinning).toEqual({
      left: [SELECT_COLUMN_ID, "column1"],
      right: ["column2"],
    });
  });

  it("should handle function updates to column pinning state", () => {
    const { result } = renderHook(() => useColumnPinning(["initialLeft"]));

    act(() => {
      result.current.setColumnPinning((prev) => ({
        ...prev,
        right: ["newRight"],
      }));
    });

    expect(result.current.columnPinning).toEqual({
      left: [SELECT_COLUMN_ID, "initialLeft"],
      right: ["newRight"],
    });
  });
});
