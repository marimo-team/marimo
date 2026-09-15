/* Copyright 2026 Marimo. All rights reserved. */
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AccordionPlugin } from "../AccordionPlugin";

const plugin = new AccordionPlugin();

function renderAccordion(multiple: boolean, expanded?: string[]) {
  return plugin.render({
    host: document.createElement("marimo-accordion"),
    data: plugin.validator.parse({
      labels: ["Summary", "Details"],
      multiple,
      expanded,
    }),
    children: [
      <p key="summary">Overview</p>,
      <p key="details">More information</p>,
    ],
  });
}

describe("AccordionPlugin", () => {
  afterEach(cleanup);

  it.each([
    { multiple: false, expanded: undefined, expected: ["false", "false"] },
    { multiple: true, expanded: [], expected: ["false", "false"] },
    { multiple: false, expanded: ["0"], expected: ["true", "false"] },
    { multiple: false, expanded: ["1"], expected: ["false", "true"] },
    { multiple: true, expanded: ["0", "1"], expected: ["true", "true"] },
  ])(
    "sets initial expansion: $multiple, $expanded",
    ({ multiple, expanded, expected }) => {
      const { getAllByRole } = render(renderAccordion(multiple, expanded));
      expect(
        getAllByRole("button").map((button) =>
          button.getAttribute("aria-expanded"),
        ),
      ).toEqual(expected);
    },
  );

  it("lets users collapse and switch the initially expanded item", () => {
    const { getAllByRole, rerender } = render(renderAccordion(false, ["1"]));
    const [summary, details] = getAllByRole("button");
    fireEvent.click(details);
    expect(details.getAttribute("aria-expanded")).toBe("false");
    rerender(renderAccordion(false, ["1"]));
    expect(details.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(details);
    fireEvent.click(summary);
    expect(
      [summary, details].map((button) => button.getAttribute("aria-expanded")),
    ).toEqual(["true", "false"]);
  });

  it("lets users collapse items independently with multiple enabled", () => {
    const { getAllByRole } = render(renderAccordion(true, ["0", "1"]));
    const [summary, details] = getAllByRole("button");
    fireEvent.click(summary);
    expect(
      [summary, details].map((button) => button.getAttribute("aria-expanded")),
    ).toEqual(["false", "true"]);
  });
});
