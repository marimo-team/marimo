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
  it("rounds floating-point artifacts in the displayed range", () => {
    const plugin = new RangeSliderPlugin();
    const props: IPluginProps<
      number[],
      z.infer<typeof RangeSliderPlugin.prototype.validator>
    > = {
      host: document.createElement("div"),
      value: [1.2, 1.500000000000001],
      setValue: vi.fn(),
      data: {
        initialValue: [1.2, 1.500000000000001],
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
      },
      functions: {},
    };

    const { getByText } = render(plugin.render(props));

    expect(getByText("1.2, 1.5")).toBeDefined();
  });
});
