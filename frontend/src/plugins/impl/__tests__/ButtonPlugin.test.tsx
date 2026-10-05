/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { IPluginProps, Setter } from "../../types";
import { ButtonPlugin } from "../ButtonPlugin";

const plugin = new ButtonPlugin();
type ButtonData = z.infer<typeof plugin.validator>;

function renderButton(data: Partial<ButtonData> = {}) {
  const setValue = vi.fn<Setter<number>>();
  const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
  const onClick = vi.fn();
  const props: IPluginProps<number, ButtonData> = {
    host: document.createElement("div"),
    value: 0,
    setValue,
    functions: {},
    data: {
      label: "Run analysis",
      kind: "neutral",
      disabled: false,
      fullWidth: false,
      ...data,
    },
  };
  render(
    <TooltipProvider>
      {/* oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- Verify that disabled clicks do not reach parent React handlers. */}
      <form onSubmit={onSubmit} onClick={onClick}>
        {plugin.render(props)}
      </form>
    </TooltipProvider>,
  );
  const button = screen.getByRole<HTMLButtonElement>("button", {
    name: "Run analysis",
  });
  return {
    button,
    setValue,
    onSubmit,
    onClick,
  };
}

describe("ButtonPlugin disabled tooltips", () => {
  it("exposes the disabled state and explanation on keyboard focus", () => {
    const { button } = renderButton({
      disabled: true,
      tooltip: "Select a dataset first",
    });
    expect(button.disabled).toBe(false);
    expect(button.getAttribute("aria-disabled")).toBe("true");
    act(() => button.focus());
    expect(document.activeElement).toBe(button);
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.textContent).toBe("Select a dataset first");
    expect(button.getAttribute("aria-describedby")).toBe(tooltip.id);

    fireEvent.keyDown(button, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it.each([undefined, ""])(
    "keeps native disabling without an explanation (%s)",
    (tooltip) => {
      const { button } = renderButton({ disabled: true, tooltip });
      expect(button.disabled).toBe(true);
      expect(button.hasAttribute("aria-disabled")).toBe(false);
      act(() => button.focus());
      expect(document.activeElement).not.toBe(button);
    },
  );

  it("blocks clicks, submission, propagation, and programmatic activation", () => {
    const { button, setValue, onSubmit, onClick } = renderButton({
      disabled: true,
      tooltip: "Select a dataset first",
    });
    expect(fireEvent.click(button)).toBe(false);
    act(() => button.click());
    expect(setValue).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(onClick).not.toHaveBeenCalled();
  });

  it("ignores keyboard shortcuts while disabled", () => {
    const { button, setValue, onSubmit } = renderButton({
      disabled: true,
      tooltip: "Select a dataset first",
      keyboardShortcut: "Ctrl-L",
    });
    const click = vi.spyOn(button, "click");
    fireEvent.keyDown(document, { key: "l", code: "KeyL", ctrlKey: true });
    expect(click).not.toHaveBeenCalled();
    expect(setValue).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("activates enabled buttons through their keyboard shortcut", () => {
    const { setValue } = renderButton({ keyboardShortcut: "Ctrl-L" });
    fireEvent.keyDown(document, { key: "l", code: "KeyL", ctrlKey: true });
    expect(setValue).toHaveBeenCalledOnce();
  });

  it("preserves enabled activation", () => {
    const { button, setValue, onSubmit } = renderButton({
      tooltip: "Run the selected analysis",
    });
    fireEvent.click(button);
    expect(setValue).toHaveBeenCalledOnce();
    const update = setValue.mock.calls[0][0];
    expect(typeof update).toBe("function");
    if (typeof update !== "function") {
      throw new Error("Expected a functional value update");
    }
    expect(update(4)).toBe(5);
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});
