/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToolbarItem } from "../toolbar";

describe("ToolbarItem keyboard activation", () => {
  it.each(["Enter", " "])(
    "keeps native %s activation out of cell navigation and calls the consumer handler",
    (key) => {
      const onCellKeyDown = vi.fn();
      const onKeyDown = vi.fn();
      render(
        <div onKeyDown={onCellKeyDown}>
          <ToolbarItem tooltip={null} onKeyDown={onKeyDown}>
            Run
          </ToolbarItem>
        </div>,
      );
      const button = screen.getByRole("button", { name: "Run" });

      expect(fireEvent.keyDown(button, { key })).toBe(true);
      expect(onCellKeyDown).not.toHaveBeenCalled();
      expect(onKeyDown).toHaveBeenCalledOnce();
      expect(onKeyDown.mock.calls[0][0].defaultPrevented).toBe(false);
    },
  );

  it.each([
    { key: "Enter", ctrlKey: true },
    { key: "Enter", metaKey: true },
    { key: "Enter", shiftKey: true },
    { key: "Enter", altKey: true },
    { key: " ", ctrlKey: true },
    { key: "ArrowLeft" },
    { key: "ArrowRight" },
    { key: "Tab" },
    { key: "Escape" },
  ])("preserves propagation for %j", (event) => {
    const onCellKeyDown = vi.fn();
    render(
      <div onKeyDown={onCellKeyDown}>
        <ToolbarItem tooltip={null}>Run</ToolbarItem>
      </div>,
    );

    expect(fireEvent.keyDown(screen.getByRole("button"), event)).toBe(true);
    expect(onCellKeyDown).toHaveBeenCalledOnce();
  });

  it("does not submit forms and preserves disabled and mouse-focus behavior", () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <ToolbarItem tooltip={null} onClick={onClick}>
        Run
      </ToolbarItem>,
    );
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("type", "button");
    expect(fireEvent.mouseDown(button)).toBe(false);
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();

    rerender(
      <ToolbarItem tooltip={null} onClick={onClick} disabled={true}>
        Run
      </ToolbarItem>,
    );
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });
});
