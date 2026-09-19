/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { RangeSlider } from "../range-slider";

vi.mock("react-aria", () => ({
  useLocale: () => ({ locale: "en-US" }),
}));

vi.mock("../tooltip", () => {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  );
  const Content = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  );

  return {
    TooltipContent: Content,
    TooltipPortal: Wrapper,
    TooltipProvider: Wrapper,
    TooltipRoot: Wrapper,
    TooltipTrigger: Wrapper,
  };
});

vi.mock("radix-ui", () => {
  const Primitive = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) => (
    <div ref={ref} {...props}>
      {children}
    </div>
  ));
  Primitive.displayName = "Primitive";

  return {
    Slider: {
      Root: Primitive,
      Track: Primitive,
      Range: Primitive,
      Thumb: Primitive,
    },
  };
});

describe("RangeSlider", () => {
  it("formats both tooltip values without floating-point artifacts", () => {
    const { getAllByText, queryByText } = render(
      <RangeSlider
        aria-label="Range"
        min={0}
        max={10}
        step={0.01}
        value={[1.2, 1.500000000000001]}
        valueMap={(value) => value}
      />,
    );

    expect(getAllByText("1.2")).toHaveLength(1);
    expect(getAllByText("1.5")).toHaveLength(1);
    expect(queryByText("1.500000000000001")).toBeNull();
  });

  it("keeps the legacy precision when no step is supplied", () => {
    const { getAllByText, queryByText } = render(
      <RangeSlider
        aria-label="Range"
        min={0}
        max={10}
        value={[1.2, 1.500000000000001]}
        valueMap={(value) => value}
      />,
    );

    expect(getAllByText("1.2")).toHaveLength(1);
    expect(getAllByText("1.5")).toHaveLength(1);
    expect(queryByText("1.500000000000001")).toBeNull();
  });

  it("preserves precision from finer-grained steps", () => {
    const { getAllByText, queryByText } = render(
      <RangeSlider
        aria-label="Range"
        min={0}
        max={10}
        step={0.001}
        value={[1.234, 1.235000000000001]}
        valueMap={(value) => value}
      />,
    );

    expect(getAllByText("1.234")).toHaveLength(1);
    expect(getAllByText("1.235")).toHaveLength(1);
    expect(queryByText("1.23")).toBeNull();
  });

  it("infers precision from custom mapped steps", () => {
    const steps = [1, 1.234, 2];
    const { getAllByText } = render(
      <RangeSlider
        aria-label="Range"
        min={0}
        max={steps.length - 1}
        step={1}
        steps={steps}
        value={[0, 1]}
        valueMap={(value) => steps[value]}
      />,
    );

    expect(getAllByText("1")).toHaveLength(1);
    expect(getAllByText("1.234")).toHaveLength(1);
  });
});
