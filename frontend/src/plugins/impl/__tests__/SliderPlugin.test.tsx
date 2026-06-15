/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import { SetupMocks } from "@/__mocks__/common";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import type { IPluginProps } from "../../types";
import { SliderPlugin } from "../SliderPlugin";

vi.mock("@/components/ui/slider", () => ({
  Slider: ({
    disabled,
    onValueChange,
    onValueCommit,
    value,
  }: {
    disabled?: boolean;
    onValueChange?: (value: number[]) => void;
    onValueCommit?: (value: number[]) => void;
    value: number[];
  }) => (
    <div>
      <button
        aria-label="Slider change"
        disabled={disabled}
        onClick={() => onValueChange?.([value[0] + 1])}
        type="button"
      />
      <button
        aria-label="Slider commit"
        disabled={disabled}
        onClick={() => onValueCommit?.(value)}
        type="button"
      />
    </div>
  ),
}));

SetupMocks.resizeObserver();

describe("SliderPlugin", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    store.set(initialModeAtom, "edit");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const createProps = ({
    debounce,
    includeInput,
    setValue,
  }: {
    debounce: boolean;
    includeInput: boolean;
    setValue: ReturnType<typeof vi.fn>;
  }): IPluginProps<
    number,
    z.infer<typeof SliderPlugin.prototype.validator>
  > => {
    return {
      host: document.createElement("div"),
      value: 5,
      setValue,
      data: {
        initialValue: 5,
        start: 0,
        stop: 10,
        step: 1,
        label: "Test Slider",
        debounce,
        orientation: "horizontal" as const,
        showValue: false,
        fullWidth: false,
        includeInput,
        steps: null,
      },
      functions: {},
    };
  };

  // When `steps` are provided, the slider works in *index* space: `value`,
  // `start`, `stop` and `step` are all indices into the `steps` array, while
  // the editable input shows/accepts the actual step values.
  const createStepsProps = ({
    steps,
    valueIndex,
    setValue,
  }: {
    steps: number[];
    valueIndex: number;
    setValue: ReturnType<typeof vi.fn>;
  }): IPluginProps<
    number,
    z.infer<typeof SliderPlugin.prototype.validator>
  > => {
    return {
      host: document.createElement("div"),
      value: valueIndex,
      setValue,
      data: {
        initialValue: valueIndex,
        start: 0,
        stop: steps.length - 1,
        step: 1,
        label: "Test Slider",
        debounce: false,
        orientation: "horizontal" as const,
        showValue: false,
        fullWidth: false,
        includeInput: true,
        steps,
      },
      functions: {},
    };
  };

  const typeAndCommit = (input: HTMLElement, value: string) => {
    act(() => {
      fireEvent.change(input, { target: { value } });
      fireEvent.blur(input);
    });
  };

  it("slider triggers setValue immediately when debounce is false", () => {
    const plugin = new SliderPlugin();
    const setValue = vi.fn();
    const props = createProps({
      debounce: false,
      includeInput: false,
      setValue,
    });
    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const changeButton = getByRole("button", { name: "Slider change" });

    act(() => {
      fireEvent.click(changeButton);
    });

    expect(setValue).toHaveBeenCalledWith(6);
  });

  it("slider waits until commit before calling setValue when debounce is true", () => {
    const plugin = new SliderPlugin();
    const setValue = vi.fn();
    const props = createProps({
      debounce: true,
      includeInput: false,
      setValue,
    });
    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    const changeButton = getByRole("button", { name: "Slider change" });
    const commitButton = getByRole("button", { name: "Slider commit" });

    act(() => {
      fireEvent.click(changeButton);
    });

    expect(setValue).not.toHaveBeenCalled();

    act(() => {
      fireEvent.click(commitButton);
    });

    expect(setValue).toHaveBeenCalledWith(6);
  });

  it("editable input triggers setValue immediately even when slider debounce is true", () => {
    const plugin = new SliderPlugin();
    const setValue = vi.fn();
    const props = createProps({ debounce: true, includeInput: true, setValue });
    const { getByRole } = render(plugin.render(props));

    act(() => {
      vi.advanceTimersByTime(0);
    });

    // The react-aria NumberField renders an input textbox.
    const numericInput = getByRole("textbox");

    act(() => {
      // Simulate typing a new value and pressing enter
      // With React-Aria NumberField, onChange fires on blur or enter
      fireEvent.change(numericInput, { target: { value: "9" } });
      fireEvent.blur(numericInput);
    });

    // Because the user explicitly typed 9 in the editable input,
    // setValue should be called immediately regardless of debounce=true.
    expect(setValue).toHaveBeenCalledWith(9);
  });

  describe("editable input with steps (regression for #9850)", () => {
    it("displays the actual step value, not the index", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      // steps[0] === -4, displayed value must be -4 (not the index 0).
      const props = createStepsProps({
        steps: [-4, -3, -2, -1],
        valueIndex: 0,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox") as HTMLInputElement;
      expect(input.value).toBe("-4");
    });

    it("displays decimal step values without float artifacts", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      const props = createStepsProps({
        steps: [0.1, 0.2, 0.3, 0.4],
        valueIndex: 2,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox") as HTMLInputElement;
      expect(input.value).toBe("0.3");
    });

    it("steps decimal input increment and decrement buttons move between steps", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      const props = createStepsProps({
        steps: [0.1, 0.2, 0.3, 0.4],
        valueIndex: 2,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const decrement = getByRole("button", {
        name: "Decrease Test Slider value input",
      });
      const increment = getByRole("button", {
        name: "Increase Test Slider value input",
      });

      expect(decrement).not.toBeDisabled();

      act(() => {
        fireEvent.click(decrement);
      });
      expect(setValue.mock.calls).toEqual([[1]]);

      act(() => {
        fireEvent.click(increment);
      });
      expect(setValue).toHaveBeenLastCalledWith(2);
    });

    it("maps a typed integer step value back to its index", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      const props = createStepsProps({
        steps: [1, 2, 3, 4],
        valueIndex: 0,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox");
      // Typing "4" should select the last step (index 3), not index 4.
      typeAndCommit(input, "4");
      expect(setValue).toHaveBeenLastCalledWith(3);

      // Typing "2" should select index 1, not get "stuck" on 3.
      typeAndCommit(input, "2");
      expect(setValue).toHaveBeenLastCalledWith(1);
    });

    it("maps fractional step values back to their index", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      const props = createStepsProps({
        steps: [0.1, 0.2, 0.3, 0.4],
        valueIndex: 0,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox");
      typeAndCommit(input, "0.3");
      expect(setValue).toHaveBeenLastCalledWith(2);
    });

    it("maps negative step values back to their index", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      const props = createStepsProps({
        steps: [-4, -3, -2, -1],
        valueIndex: 0,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox");
      typeAndCommit(input, "-2");
      expect(setValue).toHaveBeenLastCalledWith(2);
    });

    it("clamps out-of-range typed values to the nearest step index", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      const props = createStepsProps({
        steps: [1, 2, 3, 4],
        valueIndex: 0,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox");
      // Above the max step -> clamps to the last index.
      typeAndCommit(input, "100");
      expect(setValue).toHaveBeenLastCalledWith(3);
    });

    it("does not crash when steps shrink while the index is temporarily out of range", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      // Start at the last index of a 5-element steps array.
      const props = createStepsProps({
        steps: [10, 20, 30, 40, 50],
        valueIndex: 4,
        setValue,
      });
      const { getByRole, rerender } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      // Shrink `steps` so the held index (4) is now out of range. The index
      // syncs in an effect after this render, so the render must not throw on
      // the stale, out-of-range index.
      const shrunkProps = createStepsProps({
        steps: [10, 20],
        valueIndex: 1,
        setValue,
      });
      expect(() => {
        act(() => {
          rerender(plugin.render(shrunkProps));
          vi.advanceTimersByTime(0);
        });
      }).not.toThrow();

      const input = getByRole("textbox") as HTMLInputElement;
      expect(input.value).toBe("20");
    });

    it("nudges to the adjacent step on non-uniform steps even when the current step is nearest (known caveat)", () => {
      const plugin = new SliderPlugin();
      const setValue = vi.fn();
      // Non-uniform steps; start at index 2 (value 10).
      const props = createStepsProps({
        steps: [0, 1, 10, 100],
        valueIndex: 2,
        setValue,
      });
      const { getByRole } = render(plugin.render(props));

      act(() => {
        vi.advanceTimersByTime(0);
      });

      const input = getByRole("textbox");
      // 10 is far closer to 12 than 100 is, but because 12 > 10 the input nudges
      // up one index. This documents the stepper-vs-typing limitation: onChange
      // can't distinguish a typed value from a stepper-button increment.
      typeAndCommit(input, "12");
      expect(setValue).toHaveBeenLastCalledWith(3);
    });
  });
});
