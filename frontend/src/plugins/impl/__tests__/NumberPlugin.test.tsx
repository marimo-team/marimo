/* Copyright 2024 Marimo. All rights reserved. */

import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { IPluginProps } from "../../types";
import { NumberPlugin } from "../NumberPlugin";

describe("NumberPlugin", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders with initial value and updates correctly", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    // Initial render with value 5
    const props: IPluginProps<
      number | null,
      (typeof plugin)["validator"]["_type"]
    > = {
      host,
      value: 5,
      setValue,
      data: {
        start: 0,
        stop: 10,
        step: 1,
        label: null,
        debounce: false,
        fullWidth: false,
      },
      functions: {},
    };

    const { getByRole, rerender } = render(plugin.render(props));

    // Wait for React-Aria NumberField to initialize
    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;
    expect(input).toBeTruthy();
    expect(input.value).toBe("5");

    // Update to value 7
    const updatedProps = { ...props, value: 7 };
    rerender(plugin.render(updatedProps));
    expect(input.value).toBe("7");

    // Reset to value 0
    const resetProps = { ...props, value: 0 };
    rerender(plugin.render(resetProps));
    expect(input.value).toBe("0");
  });
});
