/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { copyToClipboard } from "@/utils/copy";
import { JsonOutput } from "../JsonOutput";

vi.mock("@/utils/copy", () => ({ copyToClipboard: vi.fn() }));

describe("JsonOutput interactions", () => {
  it("copies all descendants of a paginated parent and shows the real size", async () => {
    const data = { rows: Array.from({ length: 120 }, (_, i) => i) };
    const { getAllByRole, getByText } = render(
      <JsonOutput data={data} valueTypes="json" />,
    );
    expect(getByText("120 Items")).toBeInTheDocument();
    fireEvent.click(getAllByRole("button", { name: "Copy to clipboard" })[0]);
    await waitFor(() =>
      expect(copyToClipboard).toHaveBeenLastCalledWith(
        JSON.stringify(data, null, 2),
      ),
    );
  });

  it("paginates independently and resets when the data changes", () => {
    const values = Array.from({ length: 70 }, (_, i) => i);
    const { getAllByRole, queryByRole, rerender } = render(
      <JsonOutput data={{ "a.b": values, a: { b: values } }} />,
    );
    fireEvent.click(getAllByRole("button", { name: "... 40 more items" })[0]);
    expect(getAllByRole("button", { name: "... 40 more items" })).toHaveLength(
      1,
    );
    rerender(<JsonOutput data={{ values }} />);
    expect(
      queryByRole("button", { name: "... 40 more items" }),
    ).toBeInTheDocument();
  });

  it("exposes expansion controls and long text as buttons", () => {
    const text = "a".repeat(150);
    const { getByRole, getAllByRole, queryByText } = render(
      <JsonOutput data={{ text, plain: `text/plain:${text}` }} />,
    );
    const root = getByRole("button", { name: "Collapse root" });
    expect(root).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(root);
    expect(queryByText("plain")).not.toBeInTheDocument();
    fireEvent.click(getByRole("button", { name: "Expand root" }));
    const buttons = getAllByRole("button", { name: `${"a".repeat(100)}...` });
    expect(buttons).toHaveLength(2);
    fireEvent.keyDown(buttons[0], { key: "Enter" });
    expect(buttons[0]).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(buttons[0], { key: " " });
    expect(buttons[0]).toHaveAttribute("aria-expanded", "false");
  });
  it("initially collapses containers below the fifth level", () => {
    const data = {
      one: { two: { three: { four: { five: { leaf: "value" } } } } },
    };
    const { getByRole, queryByText, getByText } = render(
      <JsonOutput data={data} />,
    );
    expect(queryByText("leaf")).not.toBeInTheDocument();
    fireEvent.click(getByRole("button", { name: "Expand five" }));
    expect(getByText("leaf")).toBeInTheDocument();
  });
});
