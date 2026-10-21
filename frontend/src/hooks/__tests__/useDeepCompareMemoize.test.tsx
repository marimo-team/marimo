/* Copyright 2026 Marimo. All rights reserved. */
import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useDeepCompareMemoize } from "../useDeepCompareMemoize";

describe("useDeepCompareMemoize", () => {
  it("keeps equal values stable and updates changed values immediately", () => {
    const initial = { nested: [1, 2] };
    const { result, rerender } = renderHook(
      ({ value }) => useDeepCompareMemoize(value),
      {
        initialProps: { value: initial },
      },
    );
    rerender({ value: { nested: [1, 2] } });
    expect(result.current).toBe(initial);
    const changed = { nested: [1, 3] };
    rerender({ value: changed });
    expect(result.current).toBe(changed);
    rerender({ value: { nested: [1, 3] } });
    expect(result.current).toBe(changed);
  });

  it("handles inline callbacks without causing additional renders", () => {
    let renders = 0;
    const { result, rerender } = renderHook(
      ({ value }) => {
        renders++;
        return useDeepCompareMemoize({ callback: () => value });
      },
      { initialProps: { value: "initial" } },
    );

    const initialRenders = renders;
    rerender({ value: "changed" });
    expect(result.current.callback()).toBe("changed");
    expect(renders).toBe(initialRenders + 1);
  });
});
