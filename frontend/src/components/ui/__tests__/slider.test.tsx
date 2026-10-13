/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { Slider } from "../slider";

SetupMocks.resizeObserver();

describe("Slider", () => {
  // Regression for #2593: steps below 1e-6 stringify in exponent notation
  // ("1e-7"), which older radix versions counted as 0 decimal places, so
  // every value was rounded to an integer and the slider never moved.
  it.each([1e-6, 1e-7, 1e-9])("moves by a tiny step of %s", (step) => {
    const onValueChange = vi.fn();
    const { getByRole } = render(
      <Slider
        value={[step]}
        min={step}
        max={100 * step}
        step={step}
        onValueChange={onValueChange}
        valueMap={(v) => v}
      />,
    );

    fireEvent.keyDown(getByRole("slider"), { key: "ArrowRight" });

    expect(onValueChange).toHaveBeenCalledWith([2 * step]);
  });
});
