/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { parseShortcut } from "../shortcuts";

describe("parseShortcut", () => {
  it("should recognize single key shortcuts", () => {
    const shortcut = parseShortcut("a");
    const event = new KeyboardEvent("keydown", { key: "a" });
    expect(shortcut(event)).toBe(true);
  });

  it("should recognize combined Ctrl key shortcuts", () => {
    const shortcut = parseShortcut("Ctrl-a");
    const event = new KeyboardEvent("keydown", { key: "a", ctrlKey: true });
    expect(shortcut(event)).toBe(true);
  });

  it("should recognize combined Shift key shortcuts", () => {
    const shortcut = parseShortcut("Shift-a");
    const event = new KeyboardEvent("keydown", { key: "a", shiftKey: true });
    expect(shortcut(event)).toBe(true);
  });

  it("should recognize combined Cmd key shortcuts", () => {
    const shortcut = parseShortcut("Cmd-a");
    const event = new KeyboardEvent("keydown", { key: "a", metaKey: true });
    expect(shortcut(event)).toBe(true);
  });

  it("should recognize Space key shortcuts", () => {
    const shortcut = parseShortcut("Space");
    const event = new KeyboardEvent("keydown", { code: "Space" });
    expect(shortcut(event)).toBe(true);
  });

  it("should not recognize incorrect single key shortcuts", () => {
    const shortcut = parseShortcut("a");
    const event = new KeyboardEvent("keydown", { key: "b" });
    expect(shortcut(event)).toBe(false);
  });

  it("should not recognize incorrect combined key shortcuts", () => {
    const shortcut = parseShortcut("Ctrl-a");
    const event = new KeyboardEvent("keydown", { key: "a" }); // Missing ctrlKey
    expect(shortcut(event)).toBe(false);
  });

  it("should not recognize shortcuts with additional keys pressed", () => {
    const shortcut = parseShortcut("a");
    const event = new KeyboardEvent("keydown", { key: "a", shiftKey: true });
    expect(shortcut(event)).toBe(false);
  });

  it("should not recognize shortcuts when Shift is not part of the shortcut but is pressed", () => {
    const shortcut = parseShortcut("Ctrl-a");
    const event = new KeyboardEvent("keydown", {
      key: "a",
      ctrlKey: true,
      shiftKey: true,
    });
    expect(shortcut(event)).toBe(false);
  });

  it("should not recognize shortcuts when Ctrl is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      shiftKey: true,
      ctrlKey: true,
    });

    expect(parseShortcut("Shift-Enter")(event)).toBe(false);
    expect(parseShortcut("Ctrl-Shift-Enter")(event)).toBe(true);
  });

  it("should not recognize shortcuts when Cmd is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      shiftKey: true,
      metaKey: true,
    });

    expect(parseShortcut("Shift-Enter")(event)).toBe(false);
    expect(parseShortcut("Cmd-Shift-Enter")(event)).toBe(true);
  });

  it("should not recognize shortcuts when Alt is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      shiftKey: true,
      altKey: true,
    });

    expect(parseShortcut("Shift-Enter")(event)).toBe(false);
    expect(parseShortcut("Alt-Shift-Enter")(event)).toBe(true);
  });
});
