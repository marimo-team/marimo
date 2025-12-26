/* Copyright 2026 Marimo. All rights reserved. */

import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import type { IPluginProps } from "../../types";
import { NumberPlugin } from "../NumberPlugin";

describe("NumberPlugin", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    store.set(initialModeAtom, "edit");
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
      z.infer<(typeof plugin)["validator"]>
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

  it("handles null values correctly", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
    > = {
      host,
      value: null,
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

    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;

    // Null values should render as empty (NaN is used internally)
    expect(input.value).toBe("");
  });

  it("handles NaN values correctly", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
    > = {
      host,
      value: Number.NaN,
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

    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;

    // NaN values should be filtered to null and render as empty
    expect(input.value).toBe("");
  });

  it("handles debounce correctly", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
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

    const { getByRole, rerender } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    // setValue should not be called yet
    expect(setValue).not.toHaveBeenCalled();

    // Update the value prop to simulate a change
    const updatedProps = { ...props, value: 8 };
    rerender(plugin.render(updatedProps));

    // setValue should not be called immediately due to debounce
    expect(setValue).not.toHaveBeenCalled();

    // Advance timers by debounce delay (200ms)
    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Now verify the component can handle debounced state
    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;
    expect(input.value).toBe("8");
  });

  it("handles debounce disabled (immediate updates)", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
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

    act(() => {
      vi.advanceTimersByTime(0);
    });

    // setValue should not be called yet
    expect(setValue).not.toHaveBeenCalled();

    // Update the value prop to simulate a change
    const updatedProps = { ...props, value: 8 };
    rerender(plugin.render(updatedProps));

    // With debounce disabled, the value should update immediately without delay
    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;
    expect(input.value).toBe("8");

    // No need to advance timers since debounce is disabled
    expect(setValue).not.toHaveBeenCalled(); // setValue is only called when user interacts, not on prop changes
  });

  it("respects min and max values", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
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

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;

    expect(input.value).toBe("5");

    // Test that values above max are clamped to max
    const aboveMaxProps = { ...props, value: 15 };
    rerender(plugin.render(aboveMaxProps));
    expect(input.value).toBe("10"); // NumberField clamps to max value

    // Test that values below min are clamped to min
    const belowMinProps = { ...props, value: -5 };
    rerender(plugin.render(belowMinProps));
    expect(input.value).toBe("0"); // NumberField clamps to min value
  });

  it("handles disabled state", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
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
        disabled: true,
      },
      functions: {},
    };

    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;

    expect(input.disabled).toBe(true);
  });

  it("handles step values", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
    > = {
      host,
      value: 5,
      setValue,
      data: {
        start: 0,
        stop: 10,
        step: 0.5,
        label: null,
        debounce: false,
        fullWidth: false,
      },
      functions: {},
    };

    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;

    expect(input).toBeTruthy();
    expect(input.value).toBe("5");
  });

  it("renders with custom label", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
    > = {
      host,
      value: 5,
      setValue,
      data: {
        start: 0,
        stop: 10,
        step: 1,
        label: "Custom Label",
        debounce: false,
        fullWidth: false,
      },
      functions: {},
    };

    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Custom Label",
    }) as HTMLInputElement;

    expect(input).toBeTruthy();
  });

  it("handles transitions from null to number and back", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
    > = {
      host,
      value: null,
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

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const input = getByRole("textbox", {
      name: "Number input",
    }) as HTMLInputElement;

    expect(input.value).toBe("");

    // Update to a number
    const updatedProps = { ...props, value: 5 };
    rerender(plugin.render(updatedProps));
    expect(input.value).toBe("5");

    // Back to null
    const nullProps = { ...props, value: null };
    rerender(plugin.render(nullProps));
    expect(input.value).toBe("");
  });

  it("handles fullWidth prop", () => {
    const plugin = new NumberPlugin();
    const host = document.createElement("div");
    const setValue = vi.fn();

    const props: IPluginProps<
      number | null,
      z.infer<(typeof plugin)["validator"]>
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
        fullWidth: true,
      },
      functions: {},
    };

    const { container } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    // Check that the NumberField has the full width class
    const numberField = container.querySelector(
      '[data-testid="marimo-plugin-number-input"]',
    );
    expect(numberField?.classList.contains("w-full")).toBe(true);
  });
});
