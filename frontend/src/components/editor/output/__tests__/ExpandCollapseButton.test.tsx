/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ExpandCollapseButton } from "../ExpandCollapseButton";

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("ExpandCollapseButton", () => {
  it("should render expand icon when not expanded", () => {
    renderWithProvider(
      <ExpandCollapseButton
        isExpanded={false}
        onToggle={() => {
          // noop
        }}
      />,
    );

    const button = screen.getByTestId("expand-output-button");
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-label", "Expand output");
  });

  it("should render collapse icon when expanded", () => {
    renderWithProvider(
      <ExpandCollapseButton
        isExpanded={true}
        onToggle={() => {
          // noop
        }}
      />,
    );

    const button = screen.getByTestId("expand-output-button");
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-label", "Collapse output");
  });

  it("should call onToggle when clicked", () => {
    const onToggle = vi.fn();
    renderWithProvider(
      <ExpandCollapseButton isExpanded={false} onToggle={onToggle} />,
    );

    const button = screen.getByTestId("expand-output-button");
    fireEvent.click(button);

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("should use custom testId when provided", () => {
    renderWithProvider(
      <ExpandCollapseButton
        isExpanded={false}
        onToggle={() => {
          // noop
        }}
        testId="custom-test-id"
      />,
    );

    expect(screen.getByTestId("custom-test-id")).toBeInTheDocument();
  });

  it("should apply visibilityClassName when not expanded", () => {
    renderWithProvider(
      <ExpandCollapseButton
        isExpanded={false}
        onToggle={() => {
          // noop
        }}
        visibilityClassName="hover-action"
      />,
    );

    const button = screen.getByTestId("expand-output-button");
    expect(button.className).toContain("hover-action");
  });

  it("should not apply visibilityClassName when expanded", () => {
    renderWithProvider(
      <ExpandCollapseButton
        isExpanded={true}
        onToggle={() => {
          // noop
        }}
        visibilityClassName="hover-action"
      />,
    );

    const button = screen.getByTestId("expand-output-button");
    expect(button.className).not.toContain("hover-action");
  });
});
