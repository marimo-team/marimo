/* Copyright 2026 Marimo. All rights reserved. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutputRenderer } from "../Output";

describe("OutputRenderer renderFallback prop", () => {
  it("should use renderFallback for unsupported mimetypes", () => {
    const renderFallback = (mimetype: string) => (
      <div data-testid="custom-fallback">Custom fallback for {mimetype}</div>
    );

    render(
      <OutputRenderer
        message={{
          channel: "output",
          data: "some data",
          // @ts-expect-error - Testing fallback behavior with unsupported mimetype
          mimetype: "application/unsupported",
        }}
        renderFallback={renderFallback}
      />,
    );

    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.getByText(/Custom fallback for/)).toHaveTextContent(
      "Custom fallback for application/unsupported",
    );
  });

  it("should not use renderFallback for supported mimetypes", () => {
    const renderFallback = () => (
      <div data-testid="custom-fallback">Should not appear</div>
    );

    render(
      <OutputRenderer
        message={{
          channel: "output",
          data: "Hello World",
          mimetype: "text/plain",
        }}
        renderFallback={renderFallback}
      />,
    );

    expect(screen.queryByTestId("custom-fallback")).not.toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("should show default error when renderFallback is not provided", () => {
    render(
      <OutputRenderer
        message={{
          channel: "output",
          data: "some data",
          // @ts-expect-error - Testing default error message with unsupported mimetype
          mimetype: "application/unknown",
        }}
      />,
    );

    expect(
      screen.getByText(/Unsupported mimetype: application\/unknown/),
    ).toBeInTheDocument();
  });
});

describe("OutputRenderer image and SVG rendering", () => {
  const plainSvgString =
    '<svg><rect x="0" y="0" width="10" height="10"></rect></svg>';
  const base64SvgDataUrl =
    "data:image/svg+xml;base64,PHN2Zz48cmVjdCB4PSIwIiB5PSIw";
  const base64PngDataUrl =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB";

  it("should render plain SVG string via renderHTML", () => {
    const { container } = render(
      <OutputRenderer
        message={{
          channel: "output",
          data: plainSvgString,
          mimetype: "image/svg+xml",
        }}
      />,
    );
    const svgElement = container.querySelector("svg");
    expect(svgElement).not.toBeNull();
    const rectElement = svgElement!.querySelector("rect");
    expect(rectElement).not.toBeNull();
    const imgElement = container.querySelector("img");
    expect(imgElement).toBeNull();
  });

  it("should render Base64 SVG data URL via ImageOutput", () => {
    const { container } = render(
      <OutputRenderer
        message={{
          channel: "output",
          data: base64SvgDataUrl,
          mimetype: "image/svg+xml",
        }}
      />,
    );
    const imgElement = container.querySelector("img");
    expect(imgElement).not.toBeNull();
    expect(imgElement).toHaveAttribute("src", base64SvgDataUrl);
    const svgElement = container.querySelector("svg");
    expect(svgElement).toBeNull();
  });

  it("should render Base64 PNG data URL via ImageOutput", () => {
    const { container } = render(
      <OutputRenderer
        message={{
          channel: "output",
          data: base64PngDataUrl,
          mimetype: "image/png",
        }}
      />,
    );
    const imgElement = container.querySelector("img");
    expect(imgElement).not.toBeNull();
    expect(imgElement).toHaveAttribute("src", base64PngDataUrl);
  });
});
