/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { parseShortcut, isShortcutPressed } from "../shortcuts";

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

  it("should recognize cell.goToDefinition hotkey", () => {
    const shortcut = parseShortcut("F12");
    const event = new KeyboardEvent("keydown", { key: "F12" });
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

describe("isShortcutPressed", () => {
  it("should recognize single key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "a" });
    expect(isShortcutPressed("a", event)).toBe(true);
  });

  it("should recognize incorrect single key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "b" });
    expect(isShortcutPressed("a", event)).toBe(false);
  });

  it("should recognize combined Ctrl key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "a", ctrlKey: true });
    expect(isShortcutPressed("Ctrl-a", event)).toBe(true);
  });

  it("should recognize combined Shift key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "a", shiftKey: true });
    expect(isShortcutPressed("Shift-a", event)).toBe(true);
  });

  it("should recognize combined Cmd key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "a", metaKey: true });
    expect(isShortcutPressed("Cmd-a", event)).toBe(true);
  });

  it("should recognize Space key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { code: "Space" });
    expect(isShortcutPressed("Space", event)).toBe(true);
  });

  it("should recognize arrow key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "ArrowUp" });
    expect(isShortcutPressed("ArrowUp", event)).toBe(true);
  });

  it("should recognize keyboard hotkeys", () => {
    const event = new KeyboardEvent("keydown", { key: "F12" });
    expect(isShortcutPressed("F12", event)).toBe(true);
  });

  it("should not recognize incorrect combined key shortcuts", () => {
    const event = new KeyboardEvent("keydown", { key: "a" });
    expect(isShortcutPressed("Ctrl-a", event)).toBe(false);
  });

  it("should not recognize shortcuts with additional keys pressed", () => {
    const event = new KeyboardEvent("keydown", { key: "a", shiftKey: true });
    expect(isShortcutPressed("a", event)).toBe(false);
  });

  it("should not recognize shortcuts when Shift is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "a",
      ctrlKey: true,
      shiftKey: true,
    });
    expect(isShortcutPressed("Ctrl-a", event)).toBe(false);
  });

  it("should not recognize shortcuts when Ctrl is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      shiftKey: true,
      ctrlKey: true,
    });

    expect(isShortcutPressed("Shift-Enter", event)).toBe(false);
    expect(isShortcutPressed("Ctrl-Shift-Enter", event)).toBe(true);
  });

  it("should not recognize shortcuts when Cmd is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      shiftKey: true,
      metaKey: true,
    });

    expect(isShortcutPressed("Shift-Enter", event)).toBe(false);
    expect(isShortcutPressed("Cmd-Shift-Enter", event)).toBe(true);
  });

  it("should not recognize shortcuts when Alt is not part of the shortcut but is pressed", () => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      shiftKey: true,
      altKey: true,
    });

    expect(isShortcutPressed("Shift-Enter", event)).toBe(false);
    expect(isShortcutPressed("Alt-Shift-Enter", event)).toBe(true);
  });

  it("should recognize + as a separator", () => {
    const event = new KeyboardEvent("keydown", {
      key: "a",
      ctrlKey: true,
      shiftKey: true,
    });
    expect(isShortcutPressed("Ctrl+Shift+a", event)).toBe(true);
  });
});
