/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RunCompletionButton } from "../completion-handlers";

describe("RunCompletionButton", () => {
  const renderButton = (props: React.ComponentProps<typeof RunCompletionButton>) =>
    render(
      <TooltipProvider>
        <RunCompletionButton {...props} />
      </TooltipProvider>,
    );

  it("calls onRun when clicked", () => {
    const onRun = vi.fn();
    renderButton({ isLoading: false, onRun });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it("is disabled while loading", () => {
    renderButton({ isLoading: true, onRun: vi.fn() });
    expect(screen.getByRole("button", { name: /run/i })).toBeDisabled();
  });
});
