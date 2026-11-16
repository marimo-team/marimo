/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReadonlyDiff } from "../readonly-diff";

const mocks = vi.hoisted(() => ({
  mergeView: vi.fn(),
  useTheme: vi.fn(),
}));

vi.mock("@codemirror/merge", () => ({
  unifiedMergeView: mocks.mergeView,
}));

vi.mock("@uiw/react-codemirror", () => ({
  default: ({ theme, value }: { theme: string; value: string }) => (
    <div data-testid="code-mirror" data-theme={theme} data-value={value} />
  ),
}));

vi.mock("@/theme/useTheme", () => ({
  useTheme: mocks.useTheme,
}));

describe("ReadonlyDiff", () => {
  beforeEach(() => {
    mocks.mergeView.mockReset();
    mocks.mergeView.mockReturnValue([]);
    mocks.useTheme.mockReturnValue({ theme: "light" });
  });

  it("updates modified code without rebuilding the diff extensions", () => {
    const { rerender } = render(
      <ReadonlyDiff original="before" modified="first revision" />,
    );

    expect(screen.getByTestId("code-mirror")).toHaveAttribute(
      "data-value",
      "first revision",
    );
    expect(mocks.mergeView).toHaveBeenCalledTimes(1);

    rerender(<ReadonlyDiff original="before" modified="second revision" />);

    expect(screen.getByTestId("code-mirror")).toHaveAttribute(
      "data-value",
      "second revision",
    );
    expect(mocks.mergeView).toHaveBeenCalledTimes(1);
  });

  it("rebuilds diff extensions when the original code changes", () => {
    const { rerender } = render(
      <ReadonlyDiff original="before" modified="after" />,
    );

    rerender(<ReadonlyDiff original="earlier" modified="after" />);

    expect(mocks.mergeView).toHaveBeenCalledTimes(2);
    expect(mocks.mergeView).toHaveBeenLastCalledWith(
      expect.objectContaining({ original: "earlier" }),
    );
  });
});
