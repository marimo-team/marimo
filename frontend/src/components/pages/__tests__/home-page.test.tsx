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

function activate(link: HTMLElement, type: string, init: MouseEventInit) {
  fireEvent(link, new MouseEvent(type, { bubbles: true, ...init }));
}

describe("CreateNewNotebook", () => {
  it("links to an untitled notebook", () => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /new notebook/i });

    expect(newNotebookKey(link)).toMatch(/^__new__/);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it.each([
    { label: "click", type: "click", init: { button: 0, detail: 1 } },
    // Enter on a focused link fires `click` with detail 0
    { label: "keyboard activation", type: "click", init: { detail: 0 } },
    // ctrl/cmd-click opens a tab and still fires `click`
    { label: "ctrl-click", type: "click", init: { ctrlKey: true } },
    { label: "cmd-click", type: "click", init: { metaKey: true } },
    // middle-click opens a tab without firing `click`
    { label: "middle-click", type: "auxclick", init: { button: 1 } },
    // "Open link in new tab" from the context menu fires no click at all
    { label: "right-click", type: "contextmenu", init: { button: 2 } },
  ])("uses a fresh notebook key on every $label", ({ type, init }) => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /new notebook/i });

    const keys = new Set<string | null>([newNotebookKey(link)]);
    for (let i = 0; i < 2; i++) {
      activate(link, type, init);
      keys.add(newNotebookKey(link));
    }

    expect(keys.size).toBe(3);
  });

  it("never hands the browser a key that an earlier activation used", () => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /new notebook/i });

    // The browser reads `href` after every listener ran. Record it there.
    const followed: Array<string | null> = [];
    const record = () => followed.push(newNotebookKey(link));
    document.addEventListener("click", record);
    document.addEventListener("auxclick", record);
    try {
      activate(link, "contextmenu", { button: 2 });
      activate(link, "click", { button: 0 });
      activate(link, "click", { button: 0 });
      activate(link, "auxclick", { button: 1 });
      activate(link, "contextmenu", { button: 2 });
      activate(link, "click", { button: 0, metaKey: true });
    } finally {
      document.removeEventListener("click", record);
      document.removeEventListener("auxclick", record);
    }

    expect(followed).toHaveLength(4);
    expect(new Set(followed).size).toBe(4);
    for (const key of followed) {
      expect(key).toMatch(/^__new__s_/);
    }
  });

  it("puts a fresh key into the drag payload", () => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /new notebook/i });
    const before = newNotebookKey(link);

    const payload = new Map<string, string>();
    const dataTransfer = {
      setData: (format: string, data: string) => payload.set(format, data),
    };
    fireEvent.dragStart(link, { dataTransfer });

    const dragged = new URL(
      payload.get("text/uri-list") ?? "",
      window.location.href,
    ).searchParams.get("file");
    expect(dragged).toMatch(/^__new__s_/);
    expect(dragged).not.toBe(before);
    expect(payload.get("text/plain")).toBe(payload.get("text/uri-list"));
    // The link itself moves to the dragged key, so a later click rotates again
    expect(newNotebookKey(link)).toBe(dragged);
  });

  it("survives a re-render without reusing a key", () => {
    const { rerender } = render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: /new notebook/i });

    const keys = new Set<string | null>([newNotebookKey(link)]);
    activate(link, "click", { button: 0 });
    keys.add(newNotebookKey(link));
    rerender(<CreateNewNotebook />);
    keys.add(newNotebookKey(link));
    activate(link, "click", { button: 0 });
    keys.add(newNotebookKey(link));

    // A re-render keeps the current key; only activations rotate it
    expect(keys.size).toBe(3);
  });
});
