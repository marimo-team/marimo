/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { OutputArea, OutputRenderer } from "../Output";

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

describe("OutputArea null/undefined handling", () => {
  it("should render null when output is null", () => {
    const { container } = render(
      <TooltipProvider>
        <OutputArea
          output={null}
          cellId={cellId("test")}
          stale={false}
          loading={false}
          allowExpand={true}
        />
      </TooltipProvider>,
    );
    expect(container.innerHTML).toBe("");
  });

  it("should render null when output is undefined", () => {
    const { container } = render(
      <TooltipProvider>
        <OutputArea
          // @ts-expect-error -- testing runtime safety for undefined output
          output={undefined}
          cellId={cellId("test")}
          stale={false}
          loading={false}
          allowExpand={true}
        />
      </TooltipProvider>,
    );
    expect(container.innerHTML).toBe("");
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

describe("OutputArea fullscreen exit control", () => {
  let fullscreenElement: Element | null = null;
  const exitFullscreen = vi.fn(() => Promise.resolve());

  beforeEach(() => {
    fullscreenElement = null;
    exitFullscreen.mockClear();
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement,
    });
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: exitFullscreen,
    });
  });

  const renderOutput = () =>
    render(
      <TooltipProvider>
        <OutputArea
          output={{
            channel: "output",
            data: "Hello World",
            mimetype: "text/plain",
          }}
          cellId={cellId("test")}
          stale={false}
          loading={false}
          allowExpand={true}
        />
      </TooltipProvider>,
    );

  const enterFullscreen = (container: HTMLElement) => {
    fullscreenElement = container.querySelector('[data-cell-role="output"]');
    act(() => {
      document.dispatchEvent(new Event("fullscreenchange"));
    });
  };

  it("hides the exit button outside fullscreen", () => {
    renderOutput();
    expect(
      screen.queryByTestId("exit-fullscreen-output-button"),
    ).not.toBeInTheDocument();
  });

  it("shows the exit button when the output is the fullscreen element", () => {
    const { container } = renderOutput();
    enterFullscreen(container);
    expect(
      screen.getByTestId("exit-fullscreen-output-button"),
    ).toBeInTheDocument();
  });

  it("exits fullscreen on click", () => {
    const { container } = renderOutput();
    enterFullscreen(container);
    fireEvent.click(screen.getByTestId("exit-fullscreen-output-button"));
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
  });

  it("exits fullscreen on Escape", () => {
    const { container } = renderOutput();
    enterFullscreen(container);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
  });

  it("ignores Escape outside fullscreen", () => {
    renderOutput();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(exitFullscreen).not.toHaveBeenCalled();
  });
});
