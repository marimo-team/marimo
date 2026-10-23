/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Sidebar } from "../panel";

it("selects and deletes transforms through independent buttons", () => {
  const onSelect = vi.fn();
  const onDelete = vi.fn();
  render(
    <Sidebar
      items={[{ type: "select_columns", column_ids: [] }]}
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
