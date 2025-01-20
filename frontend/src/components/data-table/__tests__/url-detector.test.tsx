import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { UrlDetector } from "../url-detector";

describe("UrlDetector", () => {
  it("renders plain text without URLs", () => {
    render(<UrlDetector text="Hello world" />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders regular URLs as clickable links", () => {
    render(<UrlDetector text="Check https://marimo.io for more" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://marimo.io");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders multiple URLs in text", () => {
    render(
      <UrlDetector text="Visit https://marimo.io and https://github.com/marimo-team" />,
    );
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "https://marimo.io");
    expect(links[1]).toHaveAttribute("href", "https://github.com/marimo-team");
  });

  it("renders image URLs as images", () => {
    render(<UrlDetector text="Image: https://example.com/image.png" />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/image.png");
    expect(img).toHaveAttribute("alt", "URL preview");
  });

  it("renders known image domains as images", () => {
    render(
      <UrlDetector text="Avatar: https://avatars.githubusercontent.com/u/123" />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute(
      "src",
      "https://avatars.githubusercontent.com/u/123",
    );
  });

  it("falls back to link when image fails to load", () => {
    render(<UrlDetector text="Broken image: https://example.com/broken.png" />);
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
        <UrlDetector text={`Image: https://example.com/image.${ext}`} />,
      );
      const img = container.querySelector("img");
      expect(img).toHaveAttribute("src", `https://example.com/image.${ext}`);
    });
  });

  it.skip("prevents event propagation on link clicks", () => {
    const mockStopPropagation = vi.fn();
    render(<UrlDetector text="Check https://marimo.io" />);
    const link = screen.getByRole("link");

    fireEvent.click(link, {
      stopPropagation: mockStopPropagation,
    });

    expect(mockStopPropagation).toHaveBeenCalled();
  });
});
