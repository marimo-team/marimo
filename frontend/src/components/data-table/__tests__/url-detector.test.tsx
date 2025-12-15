/* Copyright 2024 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { parseContent } from "@/utils/url-parser";
import { isMarkdown, UrlDetector } from "../url-detector";

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

describe("isMarkdown", () => {
  it("returns true for headings", () => {
    expect(isMarkdown("# Heading 1")).toBe(true);
    expect(isMarkdown("## Heading 2")).toBe(true);
    expect(isMarkdown("### Heading 3")).toBe(true);
    expect(isMarkdown("Heading\n===")).toBe(true);
    expect(isMarkdown("Heading\n---")).toBe(true);
  });

  it.fails("returns true for bold text", () => {
    expect(isMarkdown("**bold**")).toBe(true);
    expect(isMarkdown("__bold__")).toBe(true);
  });

  it.fails("returns true for italic text", () => {
    expect(isMarkdown("*italic*")).toBe(true);
    expect(isMarkdown("_italic_")).toBe(true);
  });

  it("returns false for inline code", () => {
    expect(isMarkdown("`code`")).toBe(false);
    expect(isMarkdown("Text with `inline code` in it")).toBe(false);
  });

  it("returns true for code blocks", () => {
    expect(isMarkdown("```\ncode block\n```")).toBe(true);
    expect(isMarkdown("```python\ndef hello():\n    pass\n```")).toBe(true);
  });

  it("returns true for lists", () => {
    expect(isMarkdown("- item 1\n- item 2")).toBe(true);
    expect(isMarkdown("* item 1\n* item 2")).toBe(true);
    expect(isMarkdown("1. item 1\n2. item 2")).toBe(true);
  });

  it("returns true for blockquotes", () => {
    expect(isMarkdown("> This is a quote")).toBe(true);
    expect(isMarkdown("> Quote line 1\n> Quote line 2")).toBe(true);
  });

  it("returns true for horizontal rules", () => {
    expect(isMarkdown("---")).toBe(true);
    expect(isMarkdown("***")).toBe(true);
    expect(isMarkdown("___")).toBe(true);
  });

  it("returns true for tables", () => {
    expect(
      isMarkdown("| col1 | col2 |\n|------|------|\n| val1 | val2 |"),
    ).toBe(true);
  });

  it("returns true for HTML tags", () => {
    expect(isMarkdown("<div>content</div>")).toBe(true);
    expect(isMarkdown("<br />")).toBe(true);
  });

  it.fails("returns true for escaped characters", () => {
    expect(isMarkdown("\\*not bold\\*")).toBe(true);
    expect(isMarkdown("\\# not a heading")).toBe(true);
  });

  it("returns false for plain text", () => {
    expect(isMarkdown("Just plain text")).toBe(false);
    expect(isMarkdown("No markdown here")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isMarkdown("")).toBe(false);
  });

  it("returns false for plain URLs without markdown syntax", () => {
    expect(isMarkdown("https://example.com")).toBe(false);
    expect(isMarkdown("Visit https://marimo.io for more")).toBe(false);
  });

  it("returns false for plain text with numbers", () => {
    expect(isMarkdown("123 456 789")).toBe(false);
  });

  it.fails("returns true for mixed markdown and plain text", () => {
    expect(isMarkdown("Plain text with **bold** in it")).toBe(true);
    expect(isMarkdown("Start with text\n\n# Then a heading")).toBe(true);
  });

  it.fails("returns true for markdown with URLs", () => {
    expect(isMarkdown("[Link](https://example.com)")).toBe(true);
    expect(isMarkdown("Visit [marimo](https://marimo.io)")).toBe(true);
  });
});
