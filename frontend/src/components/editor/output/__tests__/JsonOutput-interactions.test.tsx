/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { copyToClipboard } from "@/utils/copy";
import { JsonOutput } from "../JsonOutput";

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

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
    expect(
      queryByRole("button", { name: "... 10 more items" }),
    ).toBeInTheDocument();
    rerender(<JsonOutput data={{ "a.b": values, a: { b: values } }} />);
    expect(
      queryByRole("button", { name: "... 10 more items" }),
    ).not.toBeInTheDocument();
    expect(getAllByRole("button", { name: "... 40 more items" })).toHaveLength(
      2,
    );
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
    const collapsedRoot = getByRole("button", { name: "Expand root" });
    expect(collapsedRoot).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(collapsedRoot);
    expect(getByRole("button", { name: "Collapse root" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(queryByText("plain")).toBeInTheDocument();
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
    const collapsed = getByRole("button", { name: "Expand five" });
    expect(collapsed).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(collapsed);
    expect(getByText("leaf")).toBeInTheDocument();
    const expanded = getByRole("button", { name: "Collapse five" });
    expect(expanded).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(expanded);
    expect(queryByText("leaf")).not.toBeInTheDocument();
    expect(getByRole("button", { name: "Expand five" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });
  it.each([null, undefined, true, 42, Number.NaN, "text"])(
    "renders scalar %j without tree state",
    (data) => {
      const { container } = render(<JsonOutput data={data} />);
      expect(container.textContent).toBe(JSON.stringify(data) ?? "");
      expect(container.querySelector(".marimo-json-output")).toBeNull();
    },
  );

  it("updates Python and JSON renderers when the mode changes", () => {
    const data = {
      yes: true,
      no: false,
      none: null,
      "text/plain+int:2": "value",
    };
    const { container, rerender } = render(<JsonOutput data={data} />);
    expect(container.textContent).toContain("True");
    expect(container.textContent).not.toContain("text/plain+int:2");
    rerender(<JsonOutput data={data} valueTypes="json" />);
    expect(container.textContent).toContain("true");
    expect(container.textContent).toContain("false");
    expect(container.textContent).toContain("null");
    expect(container.textContent).not.toContain("True");
    expect(container.textContent).toContain('"text/plain+int:2"');
    rerender(<JsonOutput data={data} valueTypes="python" />);
    expect(container.textContent).toContain("True");
    expect(container.textContent).not.toContain("text/plain+int:2");
  });

  it.each(["python", "json"] as const)(
    "copies marker-like user strings in %s mode",
    async (valueTypes) => {
      const data = {
        marker: "\u0000show_more\u000042|$",
        replacement: "<marimo-replace>None</marimo-replace>",
      };
      const { getAllByRole } = render(
        <JsonOutput data={data} valueTypes={valueTypes} />,
      );
      expect(
        getAllByRole("button", { name: "Copy to clipboard" }),
      ).toHaveLength(3);
      fireEvent.click(getAllByRole("button", { name: "Copy to clipboard" })[0]);
      await waitFor(() =>
        expect(copyToClipboard).toHaveBeenLastCalledWith(
          JSON.stringify(data, null, 2),
        ),
      );
    },
  );

  it("paginates arrays after expanding beyond the former depth cutoff", () => {
    const data = {
      a: {
        b: {
          c: {
            d: { e: { f: { rows: Array.from({ length: 100 }, (_, i) => i) } } },
          },
        },
      },
    };
    const { getByRole, getByText, queryByRole } = render(
      <JsonOutput data={data} />,
    );
    for (const name of ["e", "f", "rows"]) {
      fireEvent.click(getByRole("button", { name: `Expand ${name}` }));
    }
    expect(getByText("100 Items")).toBeInTheDocument();
    fireEvent.click(getByRole("button", { name: "... 70 more items" }));
    expect(
      getByRole("button", { name: "... 40 more items" }),
    ).toBeInTheDocument();
    expect(
      queryByRole("button", { name: "... 70 more items" }),
    ).not.toBeInTheDocument();
  });
});

describe("JsonOutput interaction regressions", () => {
  it("removes the page control after the last page without collapsing the tree", () => {
    const data = Array.from({ length: 31 }, (_, i) => i);
    const { getByRole, queryByRole, getByText } = render(
      <JsonOutput data={data} />,
    );
    fireEvent.click(getByRole("button", { name: "... 1 more items" }));
    expect(
      queryByRole("button", { name: /more items/ }),
    ).not.toBeInTheDocument();
    expect(getByRole("button", { name: "Collapse root" })).toBeInTheDocument();
    expect(getByText("31 Items")).toBeInTheDocument();
  });

  it("does not reuse a previous dataset's page size", () => {
    const matrix = Array.from({ length: 10 }, () =>
      Array.from({ length: 60 }, (_, i) => i),
    );
    const { rerender, getByRole, queryByRole } = render(
      <JsonOutput data={matrix} />,
    );
    const data = Array.from({ length: 70 }, (_, i) => i);
    rerender(<JsonOutput data={data} />);
    fireEvent.click(getByRole("button", { name: "... 40 more items" }));
    expect(
      getByRole("button", { name: "... 10 more items" }),
    ).toBeInTheDocument();
    expect(
      queryByRole("button", { name: "... 35 more items" }),
    ).not.toBeInTheDocument();
  });

  it("does not copy stale data or use the previous display mode", async () => {
    const { rerender, getAllByRole, getByRole } = render(
      <JsonOutput data={{ old: true }} />,
    );
    const data = { fresh: false, text: "text/plain:literal" };
    rerender(<JsonOutput data={data} valueTypes="json" />);
    fireEvent.click(getAllByRole("button", { name: "Copy to clipboard" })[0]);
    await waitFor(() =>
      expect(copyToClipboard).toHaveBeenLastCalledWith(
        JSON.stringify(data, null, 2),
      ),
    );
    expect(getByRole("button", { name: "Collapse root" })).toBeInTheDocument();
    rerender(<JsonOutput data={data} valueTypes="python" />);
    fireEvent.click(getAllByRole("button", { name: "Copy to clipboard" })[0]);
    await waitFor(() =>
      expect(copyToClipboard).toHaveBeenLastCalledWith(
        '{\n  "fresh": False,\n  "text": "literal"\n}',
      ),
    );
  });

  it("does not retain decoded MIME text after switching to JSON", () => {
    const data = {
      tuple: "text/plain+tuple:[42]",
      html: "text/html:<b>rich</b>",
    };
    const { container, rerender, getAllByRole } = render(
      <JsonOutput data={data} />,
    );
    expect(container.querySelector("b")).toHaveTextContent("rich");
    expect(getAllByRole("button", { name: "Copy to clipboard" })).toHaveLength(
      2,
    );
    rerender(<JsonOutput data={data} valueTypes="json" />);
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain('"tuple":"text/plain+tuple:[42]"');
    expect(container.textContent).toContain('"html":"text/html:<b>rich</b>"');
    expect(getAllByRole("button", { name: "Copy to clipboard" })).toHaveLength(
      3,
    );
  });

  it("ignores unrelated keys on long-text controls", () => {
    const text = "x".repeat(150);
    const { getByRole } = render(<JsonOutput data={{ text }} />);
    const button = getByRole("button", { name: `${"x".repeat(100)}...` });
    fireEvent.keyDown(button, { key: "Escape" });
    fireEvent.keyDown(button, { key: "ArrowDown" });
    expect(button).toHaveAttribute("aria-expanded", "false");
  });
});
