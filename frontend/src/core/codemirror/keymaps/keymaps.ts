/* Copyright 2023 Marimo. All rights reserved. */
import { KeymapConfig } from "@/core/config";
import { logNever } from "@/utils/assertNever";
import { defaultKeymap } from "@codemirror/commands";
import { Extension } from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { vim } from "@replit/codemirror-vim";

export const KEYMAP_PRESETS = ["default", "vim"] as const;

export function keymapBundle(config: KeymapConfig): Extension {
  switch (config.preset) {
    case "default":
      return [keymap.of(defaultKeymap)];
    case "vim":
      return [vim(), keymap.of(defaultKeymap)];
    default:
      logNever(config.preset);
      return [];
  }
}
