/* Copyright 2024 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { parseContent, UrlDetector } from "../url-detector";

describe("parseContent", () => {
  it("handles data URIs", () => {
    const parts = parseContent("data:image/png;base64,iVBOR");
    expect(parts).toEqual([
      {
        type: "image",
        url: "data:image/png;base64,iVBOR",
      },
    ]);
  });

  it("handles complete URLs", () => {
    const parts = parseContent("https://marimo.io/path?query=value");
    expect(parts).toEqual([
      { type: "url", url: "https://marimo.io/path?query=value" },
    ]);
  });

  it("handles multiple URLs with text", () => {
    const parts = parseContent(
      "Visit https://marimo.io and https://github.com/marimo-team",
    );
    expect(parts).toEqual([
      { type: "text", value: "Visit " },
      { type: "url", url: "https://marimo.io" },
      { type: "text", value: " and " },
      { type: "url", url: "https://github.com/marimo-team" },
    ]);
  });

  // Currently doesn't detect mixed content
  it.fails("handles text with data URIs", () => {
    const parts = parseContent("Image: data:image/png;base64,iVBOR");
    expect(parts).toEqual([
      {
        type: "text",
        value: "Image: ",
      },
      {
        type: "image",
        url: "data:image/png;base64,iVBOR",
      },
    ]);
  });

  it.fails("handles data URIs, text and images", () => {
    const parts = parseContent(
      "this is a picture: https://avatars.githubusercontent.com/u/123 and data:image/png;base64,iVBOR",
    );
    expect(parts).toEqual([
      { type: "text", value: "this is a picture: " },
      { type: "image", url: "https://avatars.githubusercontent.com/u/123" },
      { type: "text", value: " and " },
      { type: "image", url: "data:image/png;base64,iVBOR" },
    ]);
  });
});

describe("UrlDetector", () => {
  it("renders plain text without URLs", () => {
    render(<UrlDetector parts={parseContent("Hello world")} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders regular URLs as clickable links", () => {
    render(
      <UrlDetector parts={parseContent("Check https://marimo.io for more")} />,
    );
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://marimo.io");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders multiple URLs in text", () => {
    render(
      <UrlDetector
        parts={parseContent(
          "Visit https://marimo.io and https://github.com/marimo-team",
        )}
      />,
    );
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "https://marimo.io");
    expect(links[1]).toHaveAttribute("href", "https://github.com/marimo-team");
  });

  it("renders image URLs as images", () => {
    render(
      <UrlDetector
        parts={parseContent("Image: https://example.com/image.png")}
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/image.png");
    expect(img).toHaveAttribute("alt", "URL preview");
  });

  it("renders known image domains as images", () => {
    render(
      <UrlDetector
        parts={parseContent(
          "Avatar: https://avatars.githubusercontent.com/u/123",
        )}
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute(
      "src",
      "https://avatars.githubusercontent.com/u/123",
    );
  });

  it("falls back to link when image fails to load", () => {
    render(
      <UrlDetector
        parts={parseContent("Broken image: https://example.com/broken.png")}
      />,
    );
    const img = screen.getByRole("img");

    // Simulate image load error
    fireEvent.error(img);

    // Should now be a link
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://example.com/broken.png");
    expect(img).not.toBeInTheDocument();
  });

  it("handles various image extensions", () => {
    const extensions = ["png", "jpg", "jpeg", "gif", "webp", "svg", "ico"];
    extensions.forEach((ext) => {
      const { container } = render(
        <UrlDetector
          parts={parseContent(`Image: https://example.com/image.${ext}`)}
        />,
      );
      const img = container.querySelector("img");
      expect(img).toHaveAttribute("src", `https://example.com/image.${ext}`);
    });
  });

  it("renders data URIs as images", () => {
    const dataUri =
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
    render(<UrlDetector parts={parseContent(dataUri)} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", dataUri);
  });

  it.skip("prevents event propagation on link clicks", () => {
    const mockStopPropagation = vi.fn();
    render(<UrlDetector parts={parseContent("Check https://marimo.io")} />);
    const link = screen.getByRole("link");

    fireEvent.click(link, {
      stopPropagation: mockStopPropagation,
    });

    expect(mockStopPropagation).toHaveBeenCalled();
  });
});
