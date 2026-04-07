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

  const createProps = (
    debounce: boolean,
    includeInput: boolean,
    setValue: ReturnType<typeof vi.fn>,
  ): IPluginProps<number, z.infer<typeof SliderPlugin.prototype.validator>> => {
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

  it("slider triggers setValue immediately when debounce is false", () => {
    const plugin = new SliderPlugin();
    const setValue = vi.fn();
    const props = createProps(false, false, setValue);
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
    const props = createProps(true, false, setValue);
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
    const props = createProps(true, true, setValue);
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
});
