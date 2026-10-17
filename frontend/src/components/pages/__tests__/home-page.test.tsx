/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CreateNewNotebook } from "../home-page";

function newNotebookKey(link: HTMLElement): string | null {
  return new URL(
    link.getAttribute("href") ?? "",
    window.location.href,
  ).searchParams.get("file");
}

describe("CreateNewNotebook", () => {
  it("links to an untitled notebook", () => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /create a new notebook/i });

    expect(newNotebookKey(link)).toMatch(/^__new__/);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it.each([
    ["click", "click", { button: 0, detail: 1 }],
    // Enter on a focused link fires `click` with detail 0
    ["keyboard activation", "click", { button: 0, detail: 0 }],
    // middle-click opens a tab without firing `click`
    ["middle-click", "auxclick", { button: 1 }],
    // "Open link in new tab" from the context menu fires no click at all
    ["right-click", "contextmenu", { button: 2 }],
  ])("uses a fresh notebook key on every %s", (_, type, init) => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /create a new notebook/i });

    const keys = new Set<string | null>([newNotebookKey(link)]);
    for (let i = 0; i < 2; i++) {
      fireEvent(link, new MouseEvent(type, { bubbles: true, ...init }));
      keys.add(newNotebookKey(link));
    }

    expect(keys.size).toBe(3);
  });
});
