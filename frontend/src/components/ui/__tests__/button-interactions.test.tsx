/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "../button";

describe("ARIA-disabled Button", () => {
  it.each([true, "true"] as const)(
    "blocks activation for aria-disabled=%s while remaining focusable",
    (disabled) => {
      const onClick = vi.fn();
      const onSubmit = vi.fn();
      render(
        <form onSubmit={onSubmit}>
          <Button aria-disabled={disabled} onClick={onClick} type="submit">
            Run
          </Button>
        </form>,
      );
      const button = screen.getByRole<HTMLButtonElement>("button", {
        name: "Run",
      });
      act(() => button.focus());
      expect(document.activeElement).toBe(button);
      expect(fireEvent.click(button)).toBe(false);
      act(() => button.click());
      expect(onClick).not.toHaveBeenCalled();
      expect(onSubmit).not.toHaveBeenCalled();
    },
  );
});
