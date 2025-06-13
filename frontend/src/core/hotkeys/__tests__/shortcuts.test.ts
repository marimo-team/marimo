/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
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

  it("should recognize Arrow key shortcuts", () => {
    const shortcut = parseShortcut("ArrowRight");
    const event = new KeyboardEvent("keydown", { key: "ArrowRight" });
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

  it("should not recognize shortcuts when one part is missing", () => {
    const missingShift = new KeyboardEvent("keydown", {
      key: "a",
      ctrlKey: true,
    });
    const missingCtrl = new KeyboardEvent("keydown", {
      key: "a",
      shiftKey: true,
    });
    const missingSpecial = new KeyboardEvent("keydown", { key: "a" });
    const missingLetter = new KeyboardEvent("keydown", {
      ctrlKey: true,
      shiftKey: true,
    });
    const correctEvent = new KeyboardEvent("keydown", {
      key: "a",
      ctrlKey: true,
      shiftKey: true,
    });

    expect(parseShortcut("Ctrl-Shift-A")(missingShift)).toBe(false);
    expect(parseShortcut("Ctrl-Shift-A")(missingCtrl)).toBe(false);
    expect(parseShortcut("Ctrl-Shift-A")(missingSpecial)).toBe(false);
    expect(parseShortcut("Ctrl-Shift-A")(missingLetter)).toBe(false);
    expect(parseShortcut("Ctrl-Shift-A")(correctEvent)).toBe(true);
  });

  it("should recognize + as a separator", () => {
    const event = new KeyboardEvent("keydown", {
      key: "a",
      ctrlKey: true,
      shiftKey: true,
    });

    expect(parseShortcut("Ctrl+Shift+a")(event)).toBe(true);
    expect(parseShortcut("Ctrl+A")(event)).toBe(false);
  });
});
