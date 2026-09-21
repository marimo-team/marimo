/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RefreshIconButton } from "../tree-actions";

vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => children,
}));

describe("RefreshIconButton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("spins for at least 500ms after a refresh completes", async () => {
    const onClick = vi.fn().mockResolvedValue(undefined);
    const { container } = render(<RefreshIconButton onClick={onClick} />);

    fireEvent.click(screen.getByRole("button"));

    expect(onClick).toHaveBeenCalledOnce();
    expect(container.querySelector("svg")).toHaveClass("animate-[spin_0.5s]");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    expect(container.querySelector("svg")).not.toHaveClass(
      "animate-[spin_0.5s]",
    );
  });

  it("uses the latest refresh callback after a rerender", async () => {
    const initialOnClick = vi.fn().mockResolvedValue(undefined);
    const updatedOnClick = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(<RefreshIconButton onClick={initialOnClick} />);

    rerender(<RefreshIconButton onClick={updatedOnClick} />);
    fireEvent.click(screen.getByRole("button"));

    expect(initialOnClick).not.toHaveBeenCalled();
    expect(updatedOnClick).toHaveBeenCalledOnce();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
  });
});
