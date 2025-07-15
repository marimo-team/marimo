/* Copyright 2024 Marimo. All rights reserved. */

import { act, fireEvent, render } from "@testing-library/react";
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

  it("handles both immediate prop changes and debounced user input", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

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
        debounce: true,
        fullWidth: false,
      },
      functions: {},
    };

    // Initial render - setValue should be called immediately with initial value
    const { getByRole, rerender } = render(plugin.render(props));

    // Wait for React-Aria NumberField to initialize
    act(() => {
      vi.advanceTimersByTime(0);
    });

    expect(setValue).toHaveBeenCalledWith(5);

    // Clear the mock to test debounced user input
    setValue.mockClear();

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;
    expect(input).toBeTruthy();

    // Simulate user typing and committing the value
    act(() => {
      // Focus and type the value
      fireEvent.focus(input);
      // Simulate React-Aria NumberField value change
      fireEvent.change(input, { target: { value: "7" } });
      // Commit the value with Enter key
      fireEvent.keyDown(input, { key: "Enter" });
    });

    // Let React process the input
    act(() => {
      vi.advanceTimersByTime(0);
    });

    // Commit the value
    act(() => {
      fireEvent.blur(input);
    });

    // Process debounced updates
    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Should call setValue after debounce for user input
    expect(setValue).toHaveBeenCalledWith(7);

    // Clear the mock again to test immediate prop changes
    setValue.mockClear();

    // Update props - should trigger immediate setValue
    const updatedProps = { ...props, value: 3 };
    rerender(plugin.render(updatedProps));
    expect(setValue).toHaveBeenCalledWith(3);

    vi.useRealTimers();
  });
});
