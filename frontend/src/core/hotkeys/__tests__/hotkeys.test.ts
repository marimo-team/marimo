/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { type Hotkey, type HotkeyAction, HotkeyProvider } from "../hotkeys";

/**
 * Just a helper.
 */
function createHotkeys(
  keys: Partial<Record<HotkeyAction, Hotkey>>,
): Record<HotkeyAction, Hotkey> {
  return new Proxy(keys as Record<HotkeyAction, Hotkey>, {
    // biome-ignore lint: ok to have three arguments here (It's a web API)
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
