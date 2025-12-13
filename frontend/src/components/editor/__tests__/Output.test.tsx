/* Copyright 2024 Marimo. All rights reserved. */
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
