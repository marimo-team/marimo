/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { duplicateWithCtrlModifier, parseShortcut } from "../shortcuts";

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

  it("should recognize combined Cmd key shortcuts with meta or ctrl", () => {
    const shortcut = parseShortcut("Cmd-a");
    // Cmd should accept both metaKey and ctrlKey (like Mod)
    const metaEvent = new KeyboardEvent("keydown", { key: "a", metaKey: true });
    expect(shortcut(metaEvent)).toBe(true);

    const ctrlEvent = new KeyboardEvent("keydown", { key: "a", ctrlKey: true });
    expect(shortcut(ctrlEvent)).toBe(true);
  });

  it("should recognize Arrow key shortcuts", () => {
    const shortcut = parseShortcut("ArrowRight");
    const event = new KeyboardEvent("keydown", { key: "ArrowRight" });
    expect(shortcut(event)).toBe(true);
  });

  it("should recognize Mod key shortcuts", () => {
    const shortcut = parseShortcut("Mod-ArrowRight");
    const event = new KeyboardEvent("keydown", {
      key: "ArrowRight",
      metaKey: true,
      ctrlKey: false,
    });
    expect(shortcut(event)).toBe(true);

    const shortcut2 = parseShortcut("Mod-ArrowRight");
    const event2 = new KeyboardEvent("keydown", {
      key: "ArrowRight",
      ctrlKey: true,
      metaKey: false,
    });
    expect(shortcut2(event2)).toBe(true);

    vi.restoreAllMocks();
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

describe("duplicateWithCtrlModifier", () => {
  it("should duplicate Cmd binding with Ctrl variant on macOS", () => {
    // Mock macOS platform
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue("MacIntel");

    const binding = { key: "Cmd-Enter", run: () => true };
    const result = duplicateWithCtrlModifier(binding);

    expect(result).toHaveLength(2);
    expect(result[0].key).toBe("Cmd-Enter");
    expect(result[1].key).toBe("Ctrl-Enter");

    vi.restoreAllMocks();
  });

  it("should not duplicate binding without Cmd", () => {
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue("MacIntel");

    const binding = { key: "Shift-Enter", run: () => true };
    const result = duplicateWithCtrlModifier(binding);

    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("Shift-Enter");

    vi.restoreAllMocks();
  });

  it("should not duplicate Cmd-Ctrl binding to avoid Ctrl-Ctrl", () => {
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue("MacIntel");

    const binding = { key: "Cmd-Ctrl-Enter", run: () => true };
    const result = duplicateWithCtrlModifier(binding);

    // Should NOT create a Ctrl-Ctrl-Enter variant
    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("Cmd-Ctrl-Enter");

    vi.restoreAllMocks();
  });

  it("should not duplicate on non-macOS platforms", () => {
    vi.spyOn(window.navigator, "platform", "get").mockReturnValue("Win32");

    const binding = { key: "Cmd-Enter", run: () => true };
    const result = duplicateWithCtrlModifier(binding);

    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("Cmd-Enter");

    vi.restoreAllMocks();
  });
});
