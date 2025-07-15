/* Copyright 2024 Marimo. All rights reserved. */

import { defaultKeymap as originalDefaultKeymap } from "@codemirror/commands";
import { describe, expect, it } from "vitest";
import { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { visibleForTesting } from "../keymaps";

const { defaultKeymap, defaultVimKeymap, overrideKeymap, OVERRIDDEN_COMMANDS } =
  visibleForTesting;

describe("keymaps", () => {
  it("should filter out overridden commands from default keymap", () => {
    // Get the defaultKeymap function result
    const filteredKeymap = defaultKeymap();

    // Original keymap should have more entries than the filtered one
    expect(originalDefaultKeymap.length).toBeGreaterThan(filteredKeymap.length);

    // The difference should be equal to the size of OVERRIDDEN_COMMANDS
    expect(originalDefaultKeymap.length - filteredKeymap.length).toBe(
      OVERRIDDEN_COMMANDS.size,
    );

    // Verify none of the overridden commands are in the filtered keymap
    for (const binding of filteredKeymap) {
      expect(OVERRIDDEN_COMMANDS.has(binding.run)).toBe(false);
    }
  });

  it("defaultVimKeymap should remove conflicting keys", () => {
    const vimKeymap = defaultVimKeymap();
    expect(vimKeymap.length).toBeLessThan(defaultKeymap().length);
  });

  it("overrideKeymap should have the same size as OVERRIDDEN_COMMANDS", () => {
    const keys = overrideKeymap(HotkeyProvider.create());
    expect(keys.length).toBe(OVERRIDDEN_COMMANDS.size);

    for (const command of OVERRIDDEN_COMMANDS) {
      expect(keys.some((k) => k.run === command)).toBe(true);
    }
  });
});
