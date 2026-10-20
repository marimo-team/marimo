/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { useNotebookActions } from "../../actions/useNotebookActions";
import CommandPalette from "../command-palette";

vi.mock("../../actions/useNotebookActions", () => ({
  useNotebookActions: vi.fn(),
}));
vi.mock("../../actions/useCellActionButton", () => ({
  useCellActionButtons: () => [],
}));
vi.mock("../../actions/useConfigActions", () => ({
  useConfigActions: () => [],
}));

it("builds current actions only while open and keeps the opening shortcut active", async () => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
  const firstAction = vi.fn();
  const nextAction = vi.fn();
  vi.mocked(useNotebookActions).mockReturnValue([
    { label: "First action", handle: firstAction },
  ]);
  render(
    <Provider store={createStore()}>
      <CommandPalette />
    </Provider>,
  );
  expect(useNotebookActions).not.toHaveBeenCalled();

  fireEvent.keyDown(document, { key: "k", ctrlKey: true });
  await screen.findByPlaceholderText("Type to search...");
  fireEvent.click(screen.getByText("First action"));
  await waitFor(() => expect(firstAction).toHaveBeenCalledOnce());
  await waitFor(() =>
    expect(screen.queryByPlaceholderText("Type to search...")).toBeNull(),
  );

  vi.mocked(useNotebookActions)
    .mockClear()
    .mockReturnValue([{ label: "Updated action", handle: nextAction }]);
  fireEvent.keyDown(document, { key: "x" });
  expect(useNotebookActions).not.toHaveBeenCalled();

  fireEvent.keyDown(document, { key: "k", ctrlKey: true });
  await screen.findByPlaceholderText("Type to search...");
  expect(screen.queryByText("First action")).toBeNull();
  fireEvent.click(screen.getByText("Updated action"));
  await waitFor(() => expect(nextAction).toHaveBeenCalledOnce());
  expect(firstAction).toHaveBeenCalledOnce();
});
