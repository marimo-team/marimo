/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it } from "vitest";
import type { CellColumnId } from "@/core/cells/layout";
import { AddCellButtons } from "../cell-array";

it("offers only cell languages in the add-cell tray", () => {
  render(
    <Provider store={createStore()}>
      <AddCellButtons columnId={"column-1" as CellColumnId} />
    </Provider>,
  );
  expect(
    screen.getAllByRole("button").map((button) => button.textContent),
  ).toEqual(["Python", "Markdown", "SQL"]);
});
