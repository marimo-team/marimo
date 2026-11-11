/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AccordionPlugin } from "../AccordionPlugin";

describe("AccordionPlugin", () => {
  it("renders a child that has no label", () => {
    const plugin = new AccordionPlugin();
    render(
      plugin.render({
        host: document.createElement("div"),
        data: { labels: ["First"], multiple: false, expanded: [] },
        children: [<p key="first">first</p>, <p key="extra">extra</p>],
      }),
    );

    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });
});
