/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as variablesState from "@/core/variables/state";
import type { Variables } from "@/core/variables/types";
import { useDataFrameVariables } from "../useDataFrameVariables";

// Mock the useVariables hook
vi.mock("@/core/variables/state", () => ({
  useVariables: vi.fn(),
}));

describe("useDataFrameVariables", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return empty array when no variables exist", () => {
    vi.mocked(variablesState.useVariables).mockReturnValue({});

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toEqual([]);
  });

  it("should filter variables with DataFrame dataType", () => {
    const mockVariables: Variables = {
      df1: {
        name: "df1" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "DataFrame",
        value: "pandas: 10 rows x 5 cols",
      },
      x: {
        name: "x" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "int",
        value: "42",
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("df1");
    expect(result.current[0].value).toBe("pandas: 10 rows x 5 cols");
  });

  it("should filter variables with pandas: prefix in value", () => {
    const mockVariables: Variables = {
      df1: {
        name: "df1" as any,
        declaredBy: [],
        usedBy: [],
        value: "pandas: 100 rows x 10 cols",
      },
      x: {
        name: "x" as any,
        declaredBy: [],
        usedBy: [],
        value: "42",
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("df1");
  });

  it("should filter variables with polars: prefix in value", () => {
    const mockVariables: Variables = {
      df1: {
        name: "df1" as any,
        declaredBy: [],
        usedBy: [],
        value: "polars: 50 rows x 8 cols",
      },
      x: {
        name: "x" as any,
        declaredBy: [],
        usedBy: [],
        value: "42",
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("df1");
  });

  it("should handle case-insensitive value matching", () => {
    const mockVariables: Variables = {
      df1: {
        name: "df1" as any,
        declaredBy: [],
        usedBy: [],
        value: "Pandas: 100 rows x 10 cols",
      },
      df2: {
        name: "df2" as any,
        declaredBy: [],
        usedBy: [],
        value: "POLARS: 50 rows x 8 cols",
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(2);
  });

  it("should return multiple dataframes sorted by name", () => {
    const mockVariables: Variables = {
      zdf: {
        name: "zdf" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "DataFrame",
        value: "pandas: 10 rows x 5 cols",
      },
      adf: {
        name: "adf" as any,
        declaredBy: [],
        usedBy: [],
        value: "polars: 20 rows x 3 cols",
      },
      mdf: {
        name: "mdf" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "DataFrame",
        value: "pandas: 30 rows x 4 cols",
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(3);
    expect(result.current[0].name).toBe("adf");
    expect(result.current[1].name).toBe("mdf");
    expect(result.current[2].name).toBe("zdf");
  });

  it("should handle null and undefined values", () => {
    const mockVariables: Variables = {
      df1: {
        name: "df1" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "DataFrame",
        value: null,
      },
      df2: {
        name: "df2" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "DataFrame",
        value: undefined,
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(2);
    expect(result.current[0].value).toBeNull();
    expect(result.current[1].value).toBeUndefined();
  });

  it("should not include non-dataframe variables", () => {
    const mockVariables: Variables = {
      x: {
        name: "x" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "int",
        value: "42",
      },
      y: {
        name: "y" as any,
        declaredBy: [],
        usedBy: [],
        dataType: "str",
        value: "hello",
      },
      z: {
        name: "z" as any,
        declaredBy: [],
        usedBy: [],
        value: "some random value",
      },
    };

    vi.mocked(variablesState.useVariables).mockReturnValue(mockVariables);

    const { result } = renderHook(() => useDataFrameVariables());

    expect(result.current).toHaveLength(0);
  });
});
