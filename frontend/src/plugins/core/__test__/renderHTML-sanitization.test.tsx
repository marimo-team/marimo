/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHTML } from "../RenderHTML";

// Mock only the useSanitizeHtml hook, use real sanitizeHtml
vi.mock("../sanitize", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../sanitize")>();
  return {
    ...actual,
    useSanitizeHtml: vi.fn(() => false), // Default to not sanitizing based on state
  };
});

describe("renderHTML with alwaysSanitizeHtml", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("alwaysSanitizeHtml=true forces sanitization even when useSanitizeHtml=false", () => {
    const html = "<p>Test</p><script>alert('xss')</script>";
    const result = renderHTML({ html, alwaysSanitizeHtml: true });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(`"<p>Test</p>"`);
  });

  test("alwaysSanitizeHtml=false respects useSanitizeHtml=false (no sanitization)", () => {
    const html = "<p>Test</p><script>alert('test')</script>";
    const result = renderHTML({ html, alwaysSanitizeHtml: false });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<p>Test</p><script>alert('test')</script>"`,
    );
  });

  test("alwaysSanitizeHtml=false respects useSanitizeHtml=true (sanitize)", async () => {
    // Import to get access to the mock
    const sanitizeModule = await import("../sanitize");
    vi.mocked(sanitizeModule.useSanitizeHtml).mockReturnValue(true);

    const html = "<p>Test</p><script>alert('test')</script>";
    const result = renderHTML({ html, alwaysSanitizeHtml: false });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(`"<p>Test</p>"`);
  });

  test("default alwaysSanitizeHtml=true sanitizes by default", () => {
    const html = "<p>Test</p><script>alert('xss')</script>";
    // Don't pass alwaysSanitizeHtml (should default to true)
    const result = renderHTML({ html });

    const { container } = render(result);

    // Script should be removed by default sanitization
    expect(container.innerHTML).toMatchInlineSnapshot(`"<p>Test</p>"`);
  });

  test("renders sanitized content correctly", () => {
    const html = "<p>Safe content</p><script>alert('unsafe')</script>";
    const result = renderHTML({ html, alwaysSanitizeHtml: true });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(`"<p>Safe content</p>"`);
  });

  test("renders unsanitized content when allowed", () => {
    const html =
      '<p>Safe content</p><form action="//evil.com"><input type="text"></form>';
    const result = renderHTML({ html, alwaysSanitizeHtml: false });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<p>Safe content</p><form action="//evil.com"><input type="text"></form>"`,
    );
  });

  test("sanitization happens before parsing", () => {
    const html = '<p>Content</p><div onload="alert(1)">Div</div>';
    const result = renderHTML({ html, alwaysSanitizeHtml: true });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<p>Content</p><div>Div</div>"`,
    );
  });
});

describe("renderHTML sanitization integration", () => {
  test("text/markdown content should be sanitized", () => {
    const markdownHtml =
      '<span class="markdown"><p>Content</p><script>alert("xss")</script></span>';
    const result = renderHTML({ html: markdownHtml, alwaysSanitizeHtml: true });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<span class="markdown"><p>Content</p></span>"`,
    );
  });

  test("data attributes preserved with sanitization", () => {
    const richHtml = '<div data-custom="test"><p>Content</p></div>';
    const result = renderHTML({
      html: richHtml,
      alwaysSanitizeHtml: true,
    });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<div data-custom="test"><p>Content</p></div>"`,
    );
  });

  test("data attributes preserved without sanitization", () => {
    const richHtml = '<div data-custom="test"><p>Content</p></div>';
    const result = renderHTML({
      html: richHtml,
      alwaysSanitizeHtml: false,
    });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<div data-custom="test"><p>Content</p></div>"`,
    );
  });

  test("dangerous content is sanitized when alwaysSanitizeHtml=true", () => {
    const dangerousHtml = '<img src=x onerror="alert(1)"><p>Content</p>';
    const result = renderHTML({
      html: dangerousHtml,
      alwaysSanitizeHtml: true,
    });
    const { container } = render(result);
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<img src="x"><p>Content</p>"`,
    );
  });
});
