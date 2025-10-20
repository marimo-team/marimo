/* Copyright 2024 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { HtmlOutput } from "../HtmlOutput";

// Mock only the useSanitizeHtml hook, use real sanitizeHtml
vi.mock("@/plugins/core/sanitize", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/plugins/core/sanitize")>();
  return {
    ...actual,
    useSanitizeHtml: vi.fn(() => false),
  };
});

describe("HtmlOutput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders HTML content", () => {
    const result = render(
      <HtmlOutput html="<p>Hello World</p>" alwaysSanitizeHtml={false} />,
    );
    expect(result.container.firstChild).toMatchInlineSnapshot(`
      <div
        class="block"
      >
        <p>
          Hello World
        </p>
      </div>
    `);
  });

  test("renders inline when inline prop is true", () => {
    const result = render(
      <HtmlOutput
        html="<span>Inline</span>"
        inline={true}
        alwaysSanitizeHtml={false}
      />,
    );
    expect(result.container.firstChild).toMatchInlineSnapshot(`
      <div
        class="inline-flex"
      >
        <span>
          Inline
        </span>
      </div>
    `);
  });

  test("renders block by default", () => {
    const result = render(
      <HtmlOutput html="<p>Block</p>" alwaysSanitizeHtml={false} />,
    );
    expect(result.container.firstChild).toMatchInlineSnapshot(`
      <div
        class="block"
      >
        <p>
          Block
        </p>
      </div>
    `);
  });

  test("applies custom className", () => {
    const result = render(
      <HtmlOutput
        html="<p>Test</p>"
        className="custom-class"
        alwaysSanitizeHtml={false}
      />,
    );
    expect(result.container.firstChild).toMatchInlineSnapshot(`
      <div
        class="custom-class block"
      >
        <p>
          Test
        </p>
      </div>
    `);
  });

  test("handles empty html", () => {
    const { container } = render(
      <HtmlOutput html="" alwaysSanitizeHtml={false} />,
    );
    expect(container.textContent).toBe("");
  });

  test("alwaysSanitizeHtml=true sanitizes content", () => {
    const result = render(
      <HtmlOutput
        html="<p>Content</p><script>alert('test')</script>"
        alwaysSanitizeHtml={true}
      />,
    );
    expect(result.container.firstChild).toMatchInlineSnapshot(`
      <div
        class="block"
      >
        <p>
          Content
        </p>
      </div>
    `);
  });

  test("alwaysSanitizeHtml=false allows scripts when useSanitizeHtml=false", () => {
    const result = render(
      <HtmlOutput
        html="<p>Content</p><script>alert('test')</script>"
        alwaysSanitizeHtml={false}
      />,
    );
    expect(result.container.firstChild).toMatchInlineSnapshot(`
      <div
        class="block"
      >
        <p>
          Content
        </p>
        <script>
          alert('test')
        </script>
      </div>
    `);
  });
});
