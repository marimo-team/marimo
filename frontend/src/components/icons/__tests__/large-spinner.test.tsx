/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen } from "@testing-library/react";
import { Profiler } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LargeSpinner } from "../large-spinner";

describe("LargeSpinner", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("fades the old title without a second commit before the timer fires", () => {
    const onRender = vi.fn();
    const spinner = (title: string) => (
      <Profiler id="spinner" onRender={onRender}>
        <LargeSpinner title={title} />
      </Profiler>
    );
    const { rerender } = render(spinner("Starting"));
    onRender.mockClear();

    rerender(spinner("Loading"));
    expect(onRender).toHaveBeenCalledOnce();
    expect(screen.getByText("Starting")).toHaveClass("opacity-0");

    act(() => vi.advanceTimersByTime(300));
    expect(screen.getByText("Loading")).toHaveClass("opacity-100");
  });

  it("restores visibility if the title changes back during the fade", () => {
    const { rerender } = render(<LargeSpinner title="Starting" />);
    rerender(<LargeSpinner title="Loading" />);
    rerender(<LargeSpinner title="Starting" />);

    expect(screen.getByText("Starting")).toHaveClass("opacity-100");
    act(() => vi.advanceTimersByTime(300));
    expect(screen.queryByText("Loading")).not.toBeInTheDocument();
  });
});
