/* Copyright 2026 Marimo. All rights reserved. */
import type { Column } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FilterByValuesList } from "../filter-by-values-picker";

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {
    // jsdom does not implement scrollIntoView; cmdk calls it on selection.
  };
});

function mockColumn(): Column<unknown, unknown> {
  return {
    id: "name",
    columnDef: { meta: { dataType: "string" } },
  } as unknown as Column<unknown, unknown>;
}

async function calculateTopK() {
  return {
    data: [
      ["alice", 3],
      ["bob", 1],
    ] as Array<[string, number]>,
  };
}

describe("FilterByValuesList — creatable", () => {
  it("shows '+ Add \"X\"' item when creatable and query is non-empty", async () => {
    const onChange = vi.fn();
    render(
      <FilterByValuesList
        column={mockColumn()}
        calculateTopKRows={calculateTopK}
        chosenValues={new Set()}
        onChange={onChange}
        creatable={true}
      />,
    );
    await screen.findByText("alice");
    const input = screen.getByPlaceholderText(/Search or add/i);
    fireEvent.change(input, { target: { value: "carol" } });
    expect(await screen.findByText(/\+ Add "carol"/)).toBeInTheDocument();
  });

  it("commits the literal when '+ Add' is selected", async () => {
    const onChange = vi.fn();
    render(
      <FilterByValuesList
        column={mockColumn()}
        calculateTopKRows={calculateTopK}
        chosenValues={new Set()}
        onChange={onChange}
        creatable={true}
      />,
    );
    await screen.findByText("alice");
    const input = screen.getByPlaceholderText(/Search or add/i);
    fireEvent.change(input, { target: { value: "carol" } });
    fireEvent.click(await screen.findByText(/\+ Add "carol"/));
    expect(onChange).toHaveBeenCalledWith(["carol"]);
  });

  it("Enter key in creatable mode commits the query as a value", async () => {
    const onChange = vi.fn();
    render(
      <FilterByValuesList
        column={mockColumn()}
        calculateTopKRows={calculateTopK}
        chosenValues={new Set()}
        onChange={onChange}
        creatable={true}
      />,
    );
    await screen.findByText("alice");
    const input = screen.getByPlaceholderText(/Search or add/i);
    fireEvent.change(input, { target: { value: "dave" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["dave"]);
  });

  it("does NOT show '+ Add' when creatable is false", async () => {
    render(
      <FilterByValuesList
        column={mockColumn()}
        calculateTopKRows={calculateTopK}
        chosenValues={new Set()}
        onChange={vi.fn()}
        creatable={false}
      />,
    );
    await screen.findByText("alice");
    const input = screen.getByPlaceholderText(/Search among/i);
    fireEvent.change(input, { target: { value: "carol" } });
    expect(screen.queryByText(/\+ Add/)).not.toBeInTheDocument();
  });

  it("renders chosen values that are not in top-K with — count", async () => {
    render(
      <FilterByValuesList
        column={mockColumn()}
        calculateTopKRows={calculateTopK}
        chosenValues={new Set(["zara"])}
        onChange={vi.fn()}
      />,
    );
    await screen.findByText("alice");
    expect(screen.getByText("zara")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
