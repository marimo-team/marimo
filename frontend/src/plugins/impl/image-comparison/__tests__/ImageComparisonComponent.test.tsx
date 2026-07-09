/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ImageComparisonComponent from "../ImageComparisonComponent";

const baseProps = {
  beforeSrc: "before.png",
  afterSrc: "after.png",
  value: 50,
  direction: "horizontal" as const,
};

describe("ImageComparisonComponent", () => {
  it("renders the comparison slider with both images", () => {
    const { getByAltText, container } = render(
      <ImageComparisonComponent {...baseProps} />,
    );
    expect(getByAltText("Before")).toBeTruthy();
    expect(getByAltText("After")).toBeTruthy();
    expect(container.querySelector("img-comparison-slider")).toBeTruthy();
  });

  it("shows a visible error instead of collapsing when an image fails to load", () => {
    const brokenSrc = "https://example.com/does-not-exist.png";
    const { getByAltText, queryByText, container } = render(
      <ImageComparisonComponent {...baseProps} beforeSrc={brokenSrc} />,
    );

    // No error before the image fails.
    expect(queryByText(/Failed to load/)).toBeNull();

    fireEvent.error(getByAltText("Before"));

    // The slider is replaced with a visible error mentioning the source, so
    // the output is never a silent blank.
    expect(container.querySelector("img-comparison-slider")).toBeNull();
    const error = queryByText(/Failed to load image/);
    expect(error).toBeTruthy();
    expect(error?.textContent).toContain(brokenSrc);
  });

  it("truncates long sources (e.g. data URLs) in the error message", () => {
    const longSrc = `data:image/png;base64,${"A".repeat(200)}`;
    const { getByAltText, queryByText } = render(
      <ImageComparisonComponent {...baseProps} afterSrc={longSrc} />,
    );

    fireEvent.error(getByAltText("After"));

    const error = queryByText(/Failed to load image/);
    expect(error?.textContent).toContain("…");
    expect(error?.textContent).not.toContain("A".repeat(200));
  });
});
