/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, test } from "vitest";
import { Events } from "../events";

const createKeyboardEvent = (target: HTMLElement): KeyboardEvent => {
  const event = new KeyboardEvent("keydown", {
    key: "k",
    bubbles: true,
  });
  target.dispatchEvent(event);
  return event;
};

describe("Events.shouldIgnoreKeyboardEvent", () => {
  test("ignores keyboard events from marimo custom elements", () => {
    const target = document.createElement("marimo-text");
    const event = createKeyboardEvent(target);

    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
  });

  test("does not ignore keyboard events from non-input elements", () => {
    const target = document.createElement("div");
    const event = createKeyboardEvent(target);

    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(false);
  });
});
