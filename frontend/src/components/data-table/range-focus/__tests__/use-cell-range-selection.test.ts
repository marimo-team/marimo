/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { isInteractiveTarget } from "../use-cell-range-selection";

function createMouseEvent(
  target: HTMLElement,
  currentTarget: HTMLElement,
): React.MouseEvent {
  return { target, currentTarget } as unknown as React.MouseEvent;
}

describe("isInteractiveTarget", () => {
  it("returns false when target is the cell itself", () => {
    const cell = document.createElement("td");
    expect(isInteractiveTarget(createMouseEvent(cell, cell))).toBe(false);
  });

  it("returns false when clicking plain text inside a cell", () => {
    const cell = document.createElement("td");
    const span = document.createElement("span");
    cell.append(span);
    expect(isInteractiveTarget(createMouseEvent(span, cell))).toBe(false);
  });

  it.each(["input", "button", "select", "textarea"])(
    "returns true when clicking a <%s>",
    (tag) => {
      const cell = document.createElement("td");
      const el = document.createElement(tag);
      cell.append(el);
      expect(isInteractiveTarget(createMouseEvent(el, cell))).toBe(true);
    },
  );

  it("returns true when clicking an <a> link", () => {
    const cell = document.createElement("td");
    const a = document.createElement("a");
    a.href = "#";
    cell.append(a);
    expect(isInteractiveTarget(createMouseEvent(a, cell))).toBe(true);
  });

  it("returns true when clicking a <label>", () => {
    const cell = document.createElement("td");
    const label = document.createElement("label");
    cell.append(label);
    expect(isInteractiveTarget(createMouseEvent(label, cell))).toBe(true);
  });

  it('returns true for element with role="checkbox"', () => {
    const cell = document.createElement("td");
    const div = document.createElement("div");
    div.setAttribute("role", "checkbox");
    cell.append(div);
    expect(isInteractiveTarget(createMouseEvent(div, cell))).toBe(true);
  });

  it('returns true for element with role="button"', () => {
    const cell = document.createElement("td");
    const div = document.createElement("div");
    div.setAttribute("role", "button");
    cell.append(div);
    expect(isInteractiveTarget(createMouseEvent(div, cell))).toBe(true);
  });

  it('returns true for contenteditable="true"', () => {
    const cell = document.createElement("td");
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    cell.append(div);
    expect(isInteractiveTarget(createMouseEvent(div, cell))).toBe(true);
  });

  it("returns true when clicking a child nested inside an interactive element", () => {
    const cell = document.createElement("td");
    const button = document.createElement("button");
    const icon = document.createElement("span");
    button.append(icon);
    cell.append(button);
    expect(isInteractiveTarget(createMouseEvent(icon, cell))).toBe(true);
  });

  it("returns true when clicking inside a marimo-ui-element", () => {
    const cell = document.createElement("td");
    const marimoEl = document.createElement("marimo-ui-element");
    const inner = document.createElement("div");
    marimoEl.append(inner);
    cell.append(marimoEl);
    expect(isInteractiveTarget(createMouseEvent(inner, cell))).toBe(true);
  });

  it("returns true when clicking the marimo-ui-element itself", () => {
    const cell = document.createElement("td");
    const marimoEl = document.createElement("marimo-ui-element");
    cell.append(marimoEl);
    expect(isInteractiveTarget(createMouseEvent(marimoEl, cell))).toBe(true);
  });

  it.each(["marimo-lazy", "marimo-routes"])(
    "returns false when clicking inside a passive content-wrapper UIElement (%s)",
    (tag) => {
      const cell = document.createElement("td");
      const marimoEl = document.createElement("marimo-ui-element");
      const wrapper = document.createElement(tag);
      const inner = document.createElement("div");
      wrapper.append(inner);
      marimoEl.append(wrapper);
      cell.append(marimoEl);
      expect(isInteractiveTarget(createMouseEvent(inner, cell))).toBe(false);
      expect(isInteractiveTarget(createMouseEvent(wrapper, cell))).toBe(false);
    },
  );

  it.each(["marimo-slider", "marimo-button", "marimo-dropdown"])(
    "returns true when clicking inside an interactive UIElement (%s)",
    (tag) => {
      const cell = document.createElement("td");
      const marimoEl = document.createElement("marimo-ui-element");
      const widget = document.createElement(tag);
      const inner = document.createElement("div");
      widget.append(inner);
      marimoEl.append(widget);
      cell.append(marimoEl);
      expect(isInteractiveTarget(createMouseEvent(inner, cell))).toBe(true);
    },
  );

  it("returns true when an interactive UIElement is rendered alongside content wrappers", () => {
    // Genuinely interactive UIElements have their own <marimo-ui-element>
    // wrapper, so closest() finds it before reaching the outer content
    // wrapper's <marimo-ui-element>.
    const cell = document.createElement("td");
    const outerUi = document.createElement("marimo-ui-element");
    const lazy = document.createElement("marimo-lazy");
    const innerUi = document.createElement("marimo-ui-element");
    const slider = document.createElement("marimo-slider");
    const input = document.createElement("input");
    slider.append(input);
    innerUi.append(slider);
    lazy.append(innerUi);
    outerUi.append(lazy);
    cell.append(outerUi);
    expect(isInteractiveTarget(createMouseEvent(input, cell))).toBe(true);
  });

  it("returns false when clicking a non-interactive div", () => {
    const cell = document.createElement("td");
    const wrapper = document.createElement("div");
    const text = document.createElement("span");
    wrapper.append(text);
    cell.append(wrapper);
    expect(isInteractiveTarget(createMouseEvent(text, cell))).toBe(false);
  });

  it("returns false when target is a non-Element (e.g. Text node)", () => {
    const cell = document.createElement("td");
    const textNode = document.createTextNode("hello");
    cell.append(textNode);
    expect(isInteractiveTarget(createMouseEvent(textNode as never, cell))).toBe(
      false,
    );
  });
});
