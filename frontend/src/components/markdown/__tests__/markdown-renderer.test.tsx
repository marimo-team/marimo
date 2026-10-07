/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

  it("keeps supported custom URI schemes in Streamdown's link-safety flow", async () => {
    render(
      <MarkdownRenderer content="[PDF](zotero://open-pdf/library/items/IDT2EG5W)" />,
    );

    expect(await screen.findByRole("button", { name: "PDF" })).toBeInTheDocument();
  });

  it("opens the original custom URI from Streamdown's link-safety dialog", async () => {
    const url = "zotero://open-pdf/library/items/IDT2EG5W?page=1";
    const windowOpen = vi
      .spyOn(window, "open")
      .mockImplementation(() => null);

    render(<MarkdownRenderer content={`[PDF](${url})`} />);

    fireEvent.click(await screen.findByRole("button", { name: "PDF" }));

    fireEvent.click(
      await screen.findByRole("button", { name: "Open link", exact: true }),
    );

    expect(windowOpen).toHaveBeenCalledWith(url, "_blank", "noreferrer");
    windowOpen.mockRestore();
  });

  it("removes unsafe URI schemes from links", async () => {
    render(<MarkdownRenderer content="[Unsafe](javascript:alert(1))" />);

    expect(await screen.findByText(/Unsafe\s+\[blocked\]/)).toBeInTheDocument();
  });
});
