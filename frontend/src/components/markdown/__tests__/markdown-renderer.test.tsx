/* Copyright 2026 Marimo. All rights reserved. */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownRenderer } from "../markdown-renderer";

describe("MarkdownRenderer", () => {
  // Regression test for https://github.com/marimo-team/marimo/issues/9847
  it("preserves class names on raw HTML (e.g. marimo admonitions)", async () => {
    const { container } = render(
      <MarkdownRenderer
        content={
          '<div class="admonition error">' +
          '<p class="admonition-title">Error</p>' +
          "<p>Nope!</p>" +
          "</div>"
        }
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Nope!")).toBeInTheDocument();
    });

    const admonition = container.querySelector(".admonition.error");
    expect(admonition).toBeInTheDocument();
    expect(container.querySelector(".admonition-title")).toBeInTheDocument();
  });

  it("strips unsafe tags while keeping class names", async () => {
    const { container } = render(
      <MarkdownRenderer
        content={'<div class="safe"><script>alert(1)</script>hello</div>'}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("hello")).toBeInTheDocument();
    });

    expect(container.querySelector(".safe")).toBeInTheDocument();
    expect(container.querySelector("script")).not.toBeInTheDocument();
  });
});
