/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { isInteractiveTarget } from "../use-cell-range-selection";

/**
 * Dispatch a real `mousedown` from `target` (going through real DOM event
 * dispatch so `composedPath()` traverses any open shadow roots) and call
 * `isInteractiveTarget` from inside the listener, where the event's target
 * and composed path are still live.
 */
function isInteractive(target: Element, cell: Element): boolean {
  let result: boolean | undefined;
  const handler = (event: Event) => {
    const path = event.composedPath();
    result = isInteractiveTarget({
      target: event.target,
      currentTarget: cell,
      nativeEvent: {
        composedPath: () => path,
      },
    } as unknown as React.MouseEvent);
  };
  cell.addEventListener("mousedown", handler);
  target.dispatchEvent(
    new MouseEvent("mousedown", { bubbles: true, composed: true }),
  );
  cell.removeEventListener("mousedown", handler);
  if (result === undefined) {
    throw new Error("mousedown did not bubble to the cell");
  }
  return result;
}

let mounted: HTMLElement[] = [];

function makeCell(): HTMLTableCellElement {
  const table = document.createElement("table");
  const tbody = document.createElement("tbody");
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  row.append(cell);
  tbody.append(row);
  table.append(tbody);
  document.body.append(table);
  mounted.push(table);
  return cell;
}

afterEach(() => {
  for (const el of mounted) {
    el.remove();
  }
  mounted = [];
});

describe("isInteractiveTarget", () => {
  it("returns false when target is the cell itself", () => {
    const cell = makeCell();
    expect(isInteractive(cell, cell)).toBe(false);
  });

  it("returns false when clicking plain text inside a cell", () => {
    const cell = makeCell();
    const span = document.createElement("span");
    cell.append(span);
    expect(isInteractive(span, cell)).toBe(false);
  });

  it.each(["input", "button", "select", "textarea"])(
    "returns true when clicking a <%s>",
    (tag) => {
      const cell = makeCell();
      const el = document.createElement(tag);
      cell.append(el);
      expect(isInteractive(el, cell)).toBe(true);
    },
  );

  it("returns true when clicking an <a> link", () => {
    const cell = makeCell();
    const a = document.createElement("a");
    a.href = "#";
    cell.append(a);
    expect(isInteractive(a, cell)).toBe(true);
  });

  it("returns true when clicking a <label>", () => {
    const cell = makeCell();
    const label = document.createElement("label");
    cell.append(label);
    expect(isInteractive(label, cell)).toBe(true);
  });

  it.each(["checkbox", "button"])(
    'returns true for element with role="%s"',
    (role) => {
      const cell = makeCell();
      const div = document.createElement("div");
      div.setAttribute("role", role);
      cell.append(div);
      expect(isInteractive(div, cell)).toBe(true);
    },
  );

  it('returns true for contenteditable="true"', () => {
    const cell = makeCell();
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    cell.append(div);
    expect(isInteractive(div, cell)).toBe(true);
  });

  it("returns true when clicking a child nested inside an interactive element", () => {
    const cell = makeCell();
    const button = document.createElement("button");
    const icon = document.createElement("span");
    button.append(icon);
    cell.append(button);
    expect(isInteractive(icon, cell)).toBe(true);
  });

  it("returns true when clicking inside a marimo-ui-element wrapping a real widget", () => {
    const cell = makeCell();
    const marimoEl = document.createElement("marimo-ui-element");
    const widget = document.createElement("marimo-slider");
    marimoEl.append(widget);
    cell.append(marimoEl);
    expect(isInteractive(widget, cell)).toBe(true);
    expect(isInteractive(marimoEl, cell)).toBe(true);
  });

  it.each(["marimo-lazy", "marimo-routes"])(
    "returns false when clicking inside a passive content-wrapper UIElement (%s)",
    (tag) => {
      const cell = makeCell();
      const marimoEl = document.createElement("marimo-ui-element");
      const wrapper = document.createElement(tag);
      const inner = document.createElement("div");
      wrapper.append(inner);
      marimoEl.append(wrapper);
      cell.append(marimoEl);
      expect(isInteractive(inner, cell)).toBe(false);
      expect(isInteractive(wrapper, cell)).toBe(false);
    },
  );

  it("returns false when clicking plain content rendered through mo.lazy's shadow DOM (#9189)", () => {
    // Reproduces the structure marimo creates for mo.lazy(<plain html>):
    // event.target gets retargeted to <marimo-lazy>, so closest() can't see
    // into the shadow root. composedPath() must be used to confirm there's
    // no genuinely interactive descendant.
    const cell = makeCell();
    const marimoEl = document.createElement("marimo-ui-element");
    const lazy = document.createElement("marimo-lazy");
    marimoEl.append(lazy);
    cell.append(marimoEl);

    const shadow = lazy.attachShadow({ mode: "open" });
    const img = document.createElement("img");
    shadow.append(img);

    expect(isInteractive(img, cell)).toBe(false);
  });

  it("returns true when clicking an interactive widget rendered inside a content wrapper's shadow DOM", () => {
    // mo.lazy(mo.ui.slider(...)): the slider's <marimo-ui-element> lives
    // inside marimo-lazy's shadow root, so closest() from the retargeted
    // host couldn't see it. composedPath() does.
    const cell = makeCell();
    const outerUi = document.createElement("marimo-ui-element");
    const lazy = document.createElement("marimo-lazy");
    outerUi.append(lazy);
    cell.append(outerUi);

    const lazyShadow = lazy.attachShadow({ mode: "open" });
    const innerUi = document.createElement("marimo-ui-element");
    const slider = document.createElement("marimo-slider");
    innerUi.append(slider);
    lazyShadow.append(innerUi);

    const sliderShadow = slider.attachShadow({ mode: "open" });
    const input = document.createElement("input");
    input.type = "range";
    sliderShadow.append(input);

    expect(isInteractive(input, cell)).toBe(true);
  });

  it("returns false when clicking a non-interactive div", () => {
    const cell = makeCell();
    const wrapper = document.createElement("div");
    const text = document.createElement("span");
    wrapper.append(text);
    cell.append(wrapper);
    expect(isInteractive(text, cell)).toBe(false);
  });
});
