/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { SliderPlugin } from "../SliderPlugin";

SetupMocks.resizeObserver();
const plugin = new SliderPlugin();
function props(label: string | null) {
  return {
    host: document.createElement("div"),
    value: 5,
    setValue: vi.fn(),
    functions: {},
    data: plugin.validator.parse({
      initialValue: 5,
      start: 0,
      stop: 10,
      step: 1,
      steps: null,
      label,
    }),
  };
}

describe("SliderPlugin accessible labels", () => {
  test("names the actual thumb from formatted labels and updates its reference", () => {
    const initial = props("<strong>Price &amp; tax</strong>");
    const { rerender } = render(plugin.render(initial));
    const thumb = screen.getByRole("slider", { name: "Price & tax" });
    const labelId = thumb.getAttribute("aria-labelledby");
    rerender(
      plugin.render({
        ...initial,
        data: { ...initial.data, label: "Updated price" },
      }),
    );
    const updatedThumb = screen.getByRole("slider", { name: "Updated price" });
    expect(updatedThumb).toHaveAccessibleName("Updated price");
    expect(updatedThumb).toHaveAttribute("aria-labelledby", labelId);
    rerender(
      plugin.render({ ...initial, data: { ...initial.data, label: null } }),
    );
    expect(screen.getByRole("slider")).toHaveAccessibleName("Slider");
    expect(screen.getByRole("slider")).not.toHaveAttribute("aria-labelledby");
  });

  test.each([null, ""])("retains a fallback name for label %s", (label) => {
    render(plugin.render(props(label)));
    expect(screen.getByRole("slider")).toHaveAccessibleName("Slider");
  });

  test("keeps repeated widget labels independently associated", () => {
    render(
      <>
        {plugin.render(props("Price"))}
        {plugin.render(props("Price"))}
      </>,
    );
    const thumbs = screen.getAllByRole("slider", { name: "Price" });
    expect(thumbs).toHaveLength(2);
    expect(thumbs[0].getAttribute("aria-labelledby")).not.toBe(
      thumbs[1].getAttribute("aria-labelledby"),
    );
  });

  test.each([false, true])(
    "preserves keyboard commits with debounce=%s",
    (debounce) => {
      const initial = props("Price");
      render(
        plugin.render({ ...initial, data: { ...initial.data, debounce } }),
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
      expect(initial.setValue).toHaveBeenCalledWith(6);
    },
  );

  test("preserves maximum and minimum keyboard boundaries", () => {
    const initial = props("Price");
    const { rerender } = render(plugin.render({ ...initial, value: 10 }));
    fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
    expect(initial.setValue).not.toHaveBeenCalled();
    rerender(plugin.render({ ...initial, value: 0 }));
    fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowLeft" });
    expect(initial.setValue).not.toHaveBeenCalled();
  });

  test("retains the name while disabled and removes keyboard focusability", () => {
    const initial = props("Price");
    render(
      plugin.render({ ...initial, data: { ...initial.data, disabled: true } }),
    );
    const thumb = screen.getByRole("slider", { name: "Price" });
    expect(thumb).not.toHaveAttribute("tabindex");
    expect(thumb).toHaveAttribute("data-disabled");
  });

  test("preserves vertical keyboard interaction", () => {
    const initial = props("Price");
    render(
      plugin.render({
        ...initial,
        data: { ...initial.data, orientation: "vertical" },
      }),
    );
    const thumb = screen.getByRole("slider", { name: "Price" });
    expect(thumb).toHaveAttribute("aria-orientation", "vertical");
    fireEvent.keyDown(thumb, { key: "ArrowUp" });
    expect(initial.setValue).toHaveBeenCalledWith(6);
  });

  test("preserves mapped values while naming the index-space thumb", () => {
    const initial = props("Mapped price");
    render(
      plugin.render({
        ...initial,
        value: 1,
        data: {
          ...initial.data,
          start: 0,
          stop: 2,
          steps: [10, 20, 50],
          showValue: true,
        },
      }),
    );
    expect(screen.getByText("20")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("slider", { name: "Mapped price" }), {
      key: "ArrowRight",
    });
    expect(initial.setValue).toHaveBeenCalledWith(2);
    expect(screen.getByRole("slider")).toHaveAttribute("aria-valuenow", "2");
    expect(screen.getByRole("tooltip")).toHaveTextContent("50");
  });
});

describe("SliderPlugin value formatting", () => {
  test.each([
    { step: 0.125, value: 0.125, expected: "0.125" },
    { step: 0.025, value: 0.025, expected: "0.025" },
    { step: 0.125, value: 0.5, expected: "0.5" },
    { step: 0.025, value: 1, expected: "1" },
    { step: 1 / 30, value: 1 / 30, expected: "0.03" },
    { step: 1 / 30, value: 35.86666666666667, expected: "35.87" },
    { step: 0.1, value: 0.30000000000000004, expected: "0.3" },
  ])(
    "formats $value with step $step consistently",
    ({ step, value, expected }) => {
      const initial = props("Value");
      render(
        plugin.render({
          ...initial,
          value,
          data: { ...initial.data, step, stop: 60, showValue: true },
        }),
      );
      expect(screen.getByText(expected)).toBeVisible();
      const thumb = screen.getByRole("slider");
      fireEvent.focus(thumb);
      expect(screen.getByRole("tooltip")).toHaveTextContent(expected);
      expect(thumb).toHaveAttribute("aria-valuenow", String(value));
      expect(initial.setValue).not.toHaveBeenCalled();
    },
  );
});
