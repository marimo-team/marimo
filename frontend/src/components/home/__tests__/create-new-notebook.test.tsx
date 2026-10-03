/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CreateNewNotebook } from "../components";

describe("CreateNewNotebook", () => {
  it.each([
    ["click", "click", { detail: 1 }],
    ["keyboard activation", "click", { detail: 0 }],
    ["middle-click", "auxclick", { button: 1 }],
    ["context menu", "contextmenu", { button: 2 }],
  ])("creates a fresh notebook on each %s", (_, type, options) => {
    render(<CreateNewNotebook />);
    const link = screen.getByRole("link", { name: "Create a new notebook" });
    const destinations = [];

    for (let i = 0; i < 2; i++) {
      const event = new MouseEvent(type, {
        bubbles: true,
        cancelable: true,
        ...options,
      });
      expect(fireEvent(link, event)).toBe(true);
      destinations.push(link.getAttribute("href"));
    }

    expect(destinations).toEqual([
      expect.stringMatching(/\?file=__new__s_[a-z0-9]{6}$/),
      expect.stringMatching(/\?file=__new__s_[a-z0-9]{6}$/),
    ]);
    expect(new Set(destinations).size).toBe(2);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });
});
