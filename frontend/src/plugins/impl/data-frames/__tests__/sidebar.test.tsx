/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sidebar, TransformPanel } from "../panel";
import { type TransformType, TransformTypeSchema } from "../schema";

const transform: TransformType = { type: "select_columns", column_ids: [] };

it("selects and deletes transforms through independent buttons", () => {
  const onSelect = vi.fn();
  const onDelete = vi.fn();
  render(
    <Sidebar
      items={[{ id: "first", transform }]}
      selected={0}
      onSelect={onSelect}
      onDelete={onDelete}
      onAdd={vi.fn()}
    />,
  );
  const select = screen.getByRole("button", { name: "Select Columns" });
  expect(select).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(select);
  expect(onSelect).toHaveBeenCalledExactlyOnceWith(0);
  const remove = screen.getByRole("button", {
    name: "Delete Select Columns transform 1",
  });
  remove.focus();
  expect(remove).toHaveFocus();
  fireEvent.click(remove);
  expect(onDelete).toHaveBeenCalledExactlyOnceWith(0);
  expect(onSelect).toHaveBeenCalledOnce();
});

it("preserves focused rows across value edits and removal of earlier duplicates", () => {
  const first = { id: "first", transform };
  const second = { id: "second", transform };
  const props = {
    selected: 1,
    onSelect: vi.fn(),
    onDelete: vi.fn(),
    onAdd: vi.fn(),
  };
  const { rerender } = render(<Sidebar {...props} items={[first, second]} />);
  const focused = screen.getAllByRole("button", { name: "Select Columns" })[1];
  act(() => focused.focus());
  const edited = {
    ...second,
    transform: TransformTypeSchema.parse({
      ...transform,
      column_ids: ["name"],
    }),
  };
  rerender(<Sidebar {...props} items={[first, edited]} />);
  expect(screen.getAllByRole("button", { name: "Select Columns" })[1]).toBe(
    focused,
  );
  expect(focused).toHaveFocus();

  rerender(<Sidebar {...props} items={[edited]} selected={0} />);
  expect(screen.getByRole("button", { name: "Select Columns" })).toBe(focused);
  expect(focused).toHaveFocus();
  fireEvent.click(focused);
  expect(props.onSelect).toHaveBeenLastCalledWith(0);
});

it.each([
  { count: 3, removed: 0, destination: 1 },
  { count: 3, removed: 1, destination: 0 },
  { count: 3, removed: 2, destination: 1 },
  { count: 1, removed: 0, destination: undefined },
])(
  "moves focus after deleting row $removed of $count",
  ({ count, removed, destination }) => {
    function Example() {
      const [items, setItems] = useState(
        Array.from({ length: count }, (_, index) => ({
          id: `transform-${index}`,
          transform,
        })),
      );
      return (
        <Sidebar
          items={items}
          selected={undefined}
          onSelect={vi.fn()}
          onDelete={(index) =>
            setItems((current) => current.filter((_, i) => i !== index))
          }
          onAdd={vi.fn()}
        />
      );
    }
    render(<Example />);
    const selectButtons = screen.getAllByRole("button", {
      name: "Select Columns",
    });
    const target =
      destination === undefined
        ? screen.getByRole("button", { name: "Add" })
        : selectButtons[destination];
    const remove = screen.getByRole("button", {
      name: `Delete Select Columns transform ${removed + 1}`,
    });
    act(() => remove.focus());
    fireEvent.click(remove, { detail: 0 });
    expect(remove).not.toBeInTheDocument();
    expect(target).toHaveFocus();
  },
);

it("uses persistent field-array IDs in the transformation panel", () => {
  render(
    <TooltipProvider>
      <TransformPanel
        initialValue={{ transforms: [transform, transform] }}
        columns={new Map()}
        lazy={true}
        onChange={vi.fn()}
        onInvalidChange={vi.fn()}
        getColumnValues={async () => ({ values: [], too_many_values: false })}
      />
    </TooltipProvider>,
  );
  const survivor = screen.getAllByRole("button", { name: "Select Columns" })[1];
  const remove = screen.getByRole("button", {
    name: "Delete Select Columns transform 1",
  });
  act(() => remove.focus());
  fireEvent.click(remove, { detail: 0 });
  expect(screen.getByRole("button", { name: "Select Columns" })).toBe(survivor);
  expect(survivor).toHaveFocus();
  expect(survivor).toHaveAttribute("aria-pressed", "true");
});

it("does not move focus when deletion starts outside the focused row", () => {
  render(
    <>
      <input aria-label="Transform setting" />
      <Sidebar
        items={[{ id: "first", transform }]}
        selected={0}
        onSelect={vi.fn()}
        onDelete={vi.fn()}
        onAdd={vi.fn()}
      />
    </>,
  );
  const input = screen.getByRole("textbox", { name: "Transform setting" });
  act(() => input.focus());
  fireEvent.click(
    screen.getByRole("button", {
      name: "Delete Select Columns transform 1",
    }),
  );
  expect(input).toHaveFocus();
});
