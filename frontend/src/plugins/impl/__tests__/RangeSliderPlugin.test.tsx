/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import type { IPluginProps } from "../../types";
import { RangeSliderPlugin } from "../RangeSliderPlugin";

vi.mock("@/components/ui/range-slider", () => ({
  RangeSlider: () => <div data-testid="range-slider" />,
}));

vi.mock("react-aria", () => ({
  useLocale: () => ({ locale: "en-US" }),
}));

describe("RangeSliderPlugin", () => {
  type PluginProps = IPluginProps<
    number[],
    z.infer<typeof RangeSliderPlugin.prototype.validator>
  >;

  const createProps = (
    value: number[],
    data: Partial<PluginProps["data"]> = {},
  ): PluginProps => ({
    host: document.createElement("div"),
    value,
    setValue: vi.fn(),
    data: {
      initialValue: value,
      label: null,
      start: 0,
      stop: 10,
      step: 0.01,
      steps: null,
      debounce: false,
      orientation: "horizontal",
      showValue: true,
      fullWidth: true,
      disabled: false,
      ...data,
    },
    functions: {},
  });

  it("rounds floating-point artifacts in the displayed range", () => {
    const plugin = new RangeSliderPlugin();
    const props = createProps([1.2, 1.500000000000001]);

    const { getByText } = render(plugin.render(props));

    expect(getByText("1.2, 1.5")).toBeDefined();
  });

  it("preserves precision from finer-grained steps", () => {
    const plugin = new RangeSliderPlugin();
    const props = createProps([1.234, 1.235000000000001], { step: 0.001 });

    const { getByText } = render(plugin.render(props));

    expect(getByText("1.234, 1.235")).toBeDefined();
  });

  it("infers precision from custom steps", () => {
    const plugin = new RangeSliderPlugin();
    const props = createProps([0, 1], {
      stop: 2,
      step: undefined,
      steps: [1, 1.234, 2],
    });

    const { getByText } = render(plugin.render(props));

    expect(getByText("1, 1.234")).toBeDefined();
  });

  it("preserves decimals from the slider origin", () => {
    const plugin = new RangeSliderPlugin();
    const props = createProps([0.5, 1.5], { start: 0.5, stop: 10, step: 1 });

    const { getByText } = render(plugin.render(props));

    expect(getByText("0.5, 1.5")).toBeDefined();
  });
});
