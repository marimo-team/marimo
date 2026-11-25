/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Button } from "../button";

it("subscribes only while a shortcut is configured", () => {
  const add = vi.spyOn(document, "addEventListener");
  const remove = vi.spyOn(document, "removeEventListener");
  const onClick = vi.fn();
  const { rerender, unmount } = render(<Button onClick={onClick} />);
  expect(add.mock.calls.filter(([name]) => name === "keydown")).toHaveLength(0);
  rerender(<Button keyboardShortcut="shift-k" onClick={onClick} />);
  expect(add.mock.calls.filter(([name]) => name === "keydown")).toHaveLength(1);
  fireEvent.keyDown(document.body, { key: "k", shiftKey: true });
  expect(onClick).toHaveBeenCalledOnce();
  rerender(<Button onClick={onClick} />);
  expect(remove.mock.calls.filter(([name]) => name === "keydown")).toHaveLength(
    1,
  );
  unmount();
  vi.restoreAllMocks();
});
