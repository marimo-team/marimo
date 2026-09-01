/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  type Hotkey,
  type HotkeyAction,
  HotkeyProvider,
  normalizeKeyString,
  OverridingHotkeyProvider,
} from "../hotkeys";

/**
 * Just a helper.
 */
function createHotkeys(
  keys: Partial<Record<HotkeyAction, Hotkey>>,
): Record<HotkeyAction, Hotkey> {
  return new Proxy(keys as Record<HotkeyAction, Hotkey>, {
    // oxlint-ignore-next-line -- ok to have three arguments here (It's a web API)
    get(target, p, receiver) {
      const key = Reflect.get(target, p, receiver);
      if (key === "undefined") {
        throw new Error("Missing required hotkey.");
      }
      return key;
    },
  });
}

describe("HotkeyProvider platform separation", () => {
  it("should not apply Windows overrides to Linux platform", () => {
    const hotkeys = createHotkeys({
      "cell.run": {
        name: "Run cell",
        group: "Running Cells",
        key: {
          main: "Ctrl-Enter",
          windows: "Alt-Enter",
        },
      },
      "cell.runAndNewBelow": {
        name: "Run and new below",
        group: "Running Cells",
        key: "Shift-Enter",
      },
    });

    // Create providers for each platform
    const windows = new HotkeyProvider(hotkeys, { platform: "windows" });
    const linux = new HotkeyProvider(hotkeys, { platform: "linux" });
    const mac = new HotkeyProvider(hotkeys, { platform: "mac" });

    expect(windows.getHotkey("cell.run").key).toBe("Alt-Enter");
    expect(linux.getHotkey("cell.run").key).toBe("Ctrl-Enter");
    expect(mac.getHotkey("cell.run").key).toBe("Ctrl-Enter");
  });

  it("should allow each platform to have distinct keybindings", () => {
    const hotkeys = createHotkeys({
      "cell.format": {
        name: "Format cell",
        group: "Editing",
        key: {
          main: "Mod-Shift-F",
          mac: "Cmd-Option-F",
          windows: "Ctrl-Alt-F",
          linux: "Ctrl-Shift-L",
        },
      },
    });

    const windows = new HotkeyProvider(hotkeys, { platform: "windows" });
    const linux = new HotkeyProvider(hotkeys, { platform: "linux" });
    const mac = new HotkeyProvider(hotkeys, { platform: "mac" });

    // Each platform should get its own specific override
    expect(mac.getHotkey("cell.format").key).toBe("Cmd-Option-F");
    expect(windows.getHotkey("cell.format").key).toBe("Ctrl-Alt-F");
    expect(linux.getHotkey("cell.format").key).toBe("Ctrl-Shift-L");
  });
});

describe("normalizeKeyString", () => {
  it("should capitalize multi-character base key names", () => {
    expect(normalizeKeyString("Shift-enter")).toBe("Shift-Enter");
    expect(normalizeKeyString("Cmd-enter")).toBe("Cmd-Enter");
    expect(normalizeKeyString("Ctrl-backspace")).toBe("Ctrl-Backspace");
    expect(normalizeKeyString("Alt-tab")).toBe("Alt-Tab");
    expect(normalizeKeyString("Cmd-Shift-arrowUp")).toBe("Cmd-Shift-ArrowUp");
  });

  it("should leave already-correct key names unchanged", () => {
    expect(normalizeKeyString("Shift-Enter")).toBe("Shift-Enter");
    expect(normalizeKeyString("Cmd-Enter")).toBe("Cmd-Enter");
    expect(normalizeKeyString("Mod-Shift-Enter")).toBe("Mod-Shift-Enter");
  });

  it("should leave single-character keys unchanged", () => {
    expect(normalizeKeyString("Cmd-a")).toBe("Cmd-a");
    expect(normalizeKeyString("Ctrl-Shift-z")).toBe("Ctrl-Shift-z");
    expect(normalizeKeyString("a")).toBe("a");
  });

  it("should handle keys without modifiers", () => {
    expect(normalizeKeyString("enter")).toBe("Enter");
    expect(normalizeKeyString("Escape")).toBe("Escape");
    expect(normalizeKeyString("F12")).toBe("F12");
  });
});

describe("OverridingHotkeyProvider", () => {
  it("should normalize lowercase key overrides", () => {
    const provider = new OverridingHotkeyProvider(
      {
        "cell.run": "Shift-enter",
        "cell.runAndNewBelow": "Cmd-enter",
      },
      { platform: "mac" },
    );

    expect(provider.getHotkey("cell.run").key).toBe("Shift-Enter");
    expect(provider.getHotkey("cell.runAndNewBelow").key).toBe("Cmd-Enter");
  });

  it("should return defaults when no override is set", () => {
    const provider = new OverridingHotkeyProvider({}, { platform: "mac" });
    expect(provider.getHotkey("cell.run").key).toBe("Cmd-Enter");
    expect(provider.getHotkey("cell.runAndNewBelow").key).toBe("Shift-Enter");
  });

  it("should pass through correctly-cased overrides unchanged", () => {
    const provider = new OverridingHotkeyProvider(
      { "cell.run": "Shift-Enter" },
      { platform: "mac" },
    );
    expect(provider.getHotkey("cell.run").key).toBe("Shift-Enter");
  });

  it("should treat an empty override as disabling the hotkey", () => {
    const provider = new OverridingHotkeyProvider(
      { "command.enterCommandMode": "" },
      { platform: "mac" },
    );
    expect(provider.getHotkey("command.enterCommandMode").key).toBe("");
  });

  it("should fall back to the default when an override is undefined", () => {
    const provider = new OverridingHotkeyProvider(
      { "command.enterCommandMode": undefined },
      { platform: "mac" },
    );
    expect(provider.getHotkey("command.enterCommandMode").key).toBe("Escape");
  });

  it("should resolve the vim command mode shortcut per platform", () => {
    // The shortcuts dialog advertises this key, so it must come from the
    // provider rather than a hardcoded guess: Windows differs from mac/linux.
    const key = (platform: "mac" | "windows" | "linux") =>
      new OverridingHotkeyProvider({}, { platform }).getHotkey(
        "command.vimEnterCommandMode",
      ).key;
    expect(key("windows")).toBe("Shift-Escape");
    expect(key("mac")).toBe("Cmd-Escape");
    expect(key("linux")).toBe("Ctrl-Escape");
  });

  it("should remap the command mode shortcut", () => {
    const provider = new OverridingHotkeyProvider(
      { "command.enterCommandMode": "Shift-escape" },
      { platform: "mac" },
    );
    expect(provider.getHotkey("command.enterCommandMode").key).toBe(
      "Shift-Escape",
    );
  });
});
