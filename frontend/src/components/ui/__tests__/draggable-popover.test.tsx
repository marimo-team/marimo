/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { DraggablePopover } from "../draggable-popover";

it("moves from the keyboard handle without intercepting child input arrows", () => {
  render(
    <DraggablePopover open={true}>
      <input aria-label="Filter" />
    </DraggablePopover>,
  );
  const handle = screen.getByRole("button", {
    name: "Move popup with arrow keys",
  });
  const popup = screen.getByRole("dialog");
  fireEvent.keyDown(handle, { key: "ArrowRight" });
  fireEvent.keyDown(handle, { key: "ArrowDown" });
  expect(popup).toHaveStyle({ left: "10px", top: "10px" });
  expect(
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "ArrowLeft" }),
  ).toBe(true);
  expect(popup).toHaveStyle({ left: "10px", top: "10px" });
});
