/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ConnectionState } from "@/core/session/types";
import { CreateCellButton } from "../CreateCellButton";

vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({ createCell: vi.fn(), addSetupCell: vi.fn() }),
}));

it("mounts menus only on demand and restores keyboard focus to the same button", async () => {
  const onClick = vi.fn();
  const add = vi.spyOn(document, "addEventListener");
  render(
    <TooltipProvider>
      {Array.from({ length: 20 }, (_, i) => (
        <CreateCellButton
          key={i}
          connectionState={ConnectionState.OPEN}
          onClick={onClick}
          tooltipContent="Add cell"
          oneClickShortcut="shift"
        />
      ))}
    </TooltipProvider>,
  );
  expect(add.mock.calls.filter(([name]) => name === "keydown")).toHaveLength(0);
  add.mockClear();
  fireEvent.keyDown(document.body, { key: "a" });
  expect(add).not.toHaveBeenCalled();
  const button = screen.getAllByTestId("create-cell-button")[0];
  fireEvent.pointerDown(button, { button: 0 });
  expect(onClick).toHaveBeenCalledWith({ code: "" });
  button.focus();
  fireEvent.keyDown(button, { key: "ArrowDown" });
  expect(
    await screen.findByRole("menuitem", { name: "SQL cell" }),
  ).toBeTruthy();
  expect(screen.getAllByTestId("create-cell-button")[0]).toBe(button);
  fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(button));
  fireEvent.contextMenu(button);
  expect(
    await screen.findByRole("menuitem", { name: /Markdown cell/ }),
  ).toBeTruthy();
  add.mockRestore();
});
