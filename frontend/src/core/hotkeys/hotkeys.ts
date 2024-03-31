/* Copyright 2024 Marimo. All rights reserved. */
import { isPlatformMac } from "@/core/hotkeys/shortcuts";
import { Objects } from "@/utils/objects";

interface Hotkey {
  name: string;
  /**
   * Grouping for the command palette and keyboard shortcuts page.
   * If not specified, the command will not be shown in the command palette.
   */
  group: HotkeyGroup | undefined;
  key:
    | string
    | {
        main: string;
        /** macOS specific override */
        mac?: string;
        /** Windows specific override */
        windows?: string;
        /** Linux specific override */
        linux?: string;
      };
}

interface ResolvedHotkey {
  name: string;
  key: string;
}

type Platform = "mac" | "windows" | "linux";

export type HotkeyGroup =
  | "Running Cells"
  | "Creation and Ordering"
  | "Navigation"
  | "Editing"
  | "Other";

const DEFAULT_HOT_KEY = {
  // Cell Navigation
  "cell.focusUp": {
    name: "Focus up",
    group: "Navigation",
    key: "Mod-Shift-k",
  },
  "cell.focusDown": {
    name: "Focus down",
    group: "Navigation",
    key: "Mod-Shift-j",
  },

  // Creation and Ordering
  "cell.moveUp": {
    name: "Move up",
    group: "Creation and Ordering",
    key: "Mod-Shift-9",
  },
  "cell.moveDown": {
    name: "Move down",
    group: "Creation and Ordering",
    key: "Mod-Shift-0",
  },
  "cell.createAbove": {
    name: "Create cell above",
    group: "Creation and Ordering",
    key: "Mod-Shift-o",
  },
  "cell.createBelow": {
    name: "Create cell below",
    group: "Creation and Ordering",
    key: "Mod-Shift-p",
  },
  "cell.sendToTop": {
    name: "Send to top",
    group: "Creation and Ordering",
    key: "Mod-Shift-1",
  },
  "cell.sendToBottom": {
    name: "Send to bottom",
    group: "Creation and Ordering",
    key: "Mod-Shift-2",
  },

  // Running Cells
  "cell.run": {
    name: "Run",
    group: "Running Cells",
    key: "Mod-Enter",
  },
  "cell.runAndNewBelow": {
    name: "Run and new below",
    group: "Running Cells",
    key: "Shift-Enter",
  },
  "cell.runAndNewAbove": {
    name: "Run and new above",
    group: "Running Cells",
    key: "Mod-Shift-Enter",
  },

  // Editing Cells
  "cell.format": {
    name: "Format",
    group: "Editing",
    key: "Mod-b",
  },
  "cell.viewAsMarkdown": {
    name: "View as Markdown",
    group: "Editing",
    key: "Mod-Shift-m",
  },
  "cell.complete": {
    name: "Code completion",
    group: "Editing",
    key: "Ctrl-Space",
  },
  "cell.undo": {
    name: "Undo",
    group: "Editing",
    key: "Mod-z",
  },
  "cell.redo": {
    name: "Redo",
    group: "Editing",
    key: {
      main: "Mod-Shift-z",
      windows: "Mod-y",
    },
  },
  "cell.findAndReplace": {
    name: "Find and replace",
    group: "Editing",
    key: "Mod-f",
  },
  "cell.selectNextOccurrence": {
    name: "Select next occurrence",
    group: "Editing",
    key: "Mod-d",
  },
  "cell.fold": {
    name: "Fold",
    group: "Editing",
    key: {
      main: "Mod-Alt-[",
      windows: "Mod-Shift-[",
    },
  },
  "cell.unfold": {
    name: "Unfold",
    group: "Editing",
    key: {
      main: "Mod-Alt-]",
      windows: "Mod-Shift-]",
    },
  },
  "cell.foldAll": {
    name: "Fold all in cell",
    group: "Editing",
    key: "Ctrl-Alt-[",
  },
  "cell.unfoldAll": {
    name: "Unfold all in cell",
    group: "Editing",
    key: "Ctrl-Alt-]",
  },
  "cell.delete": {
    name: "Delete empty cell",
    group: "Editing",
    key: "Shift-Backspace",
  },
  "cell.hideCode": {
    name: "Hide cell code",
    group: "Editing",
    key: "Mod-h",
  },
  "cell.aiCompletion": {
    name: "AI completion",
    group: "Editing",
    key: "Mod-Shift-e",
  },
  "cell.cellActions": {
    name: "Open cell actions",
    group: "Editing",
    key: "Mod-p",
  },

  // Global Actions
  "global.hideCode": {
    name: "Toggle app view",
    group: "Other",
    key: "Mod-.",
  },
  "global.foldCode": {
    name: "Fold all cells",
    group: "Editing",
    key: {
      main: "Ctrl-Cmd-l",
      windows: "Mod-Shift-l",
    },
  },
  "global.unfoldCode": {
    name: "Unfold all cells",
    group: "Editing",
    key: {
      main: "Ctrl-Cmd-;",
      windows: "Mod-Shift-:",
    },
  },
  "global.showHelp": {
    name: "Keyboard shortcuts",
    group: "Other",
    key: "Mod-Shift-h",
  },
  "global.save": {
    name: "Save",
    group: "Other",
    key: "Mod-s",
  },
  "global.commandPalette": {
    name: "Command palette",
    group: "Other",
    key: "Mod-k",
  },
  "global.runStale": {
    name: "Run all modified cells",
    group: "Running Cells",
    key: "Mod-Shift-r",
  },
  "global.interrupt": {
    name: "Stop (interrupt) execution",
    group: "Running Cells",
    key: "Mod-i",
  },
  "global.formatAll": {
    name: "Format all",
    group: "Editing",
    key: "Mod-Shift-b",
  },
  "global.toggleLanguage": {
    name: "Toggle language to markdown (if supported)",
    group: "Editing",
    key: "F4",
  },

  // Global Navigation
  "global.focusTop": {
    name: "Focus top",
    group: "Navigation",
    key: "Mod-Shift-f",
  },
  "global.focusBottom": {
    name: "Focus bottom",
    group: "Navigation",
    key: "Mod-Shift-g",
  },
  "global.toggleSidebar": {
    name: "Toggle helper panel",
    group: "Navigation",
    key: "Mod-Shift-s",
  },
} satisfies Record<string, Hotkey>;

export type HotkeyAction = keyof typeof DEFAULT_HOT_KEY;

export function isHotkeyAction(x: string): x is HotkeyAction {
  return x in DEFAULT_HOT_KEY;
}

export interface IHotkeyProvider {
  getHotkey(action: HotkeyAction): ResolvedHotkey;
}

export class HotkeyProvider implements IHotkeyProvider {
  private mod: string;
  private platform: Platform;

  static create(isMac?: boolean): HotkeyProvider {
    return new HotkeyProvider(DEFAULT_HOT_KEY, isMac);
  }

  constructor(
    private hotkeys: Record<HotkeyAction, Hotkey>,
    isMac?: boolean,
  ) {
    isMac = isMac ?? isPlatformMac();

    this.mod = isMac ? "Cmd" : "Ctrl";
    this.platform = isMac ? "mac" : "windows";
  }

  iterate(): HotkeyAction[] {
    return Objects.keys(this.hotkeys);
  }

  getHotkey(action: HotkeyAction): ResolvedHotkey {
    const { name, key } = this.hotkeys[action];
    if (typeof key === "string") {
      return {
        name,
        key: key.replace("Mod", this.mod),
      };
    }
    const platformKey = key[this.platform] || key.main;
    return {
      name,
      key: platformKey.replace("Mod", this.mod),
    };
  }

  getHotkeyDisplay(action: HotkeyAction): string {
    return this.hotkeys[action].name;
  }

  getHotkeyGroups(): Record<HotkeyGroup, HotkeyAction[]> {
    return Objects.groupBy(
      Objects.entries(this.hotkeys),
      ([, hotkey]) => hotkey.group,
      ([action]) => action,
    );
  }
}

export class OverridingHotkeyProvider extends HotkeyProvider {
  constructor(
    private readonly overrides: Partial<
      Record<HotkeyAction, string | undefined>
    >,
  ) {
    super(DEFAULT_HOT_KEY);
  }

  override getHotkey(action: HotkeyAction): ResolvedHotkey {
    const base = super.getHotkey(action);
    const key = this.overrides[action] || base.key;
    return {
      name: base.name,
      key,
    };
  }
}

export const HOTKEYS = new OverridingHotkeyProvider({
  // Override default hotkeys here.
  // This can be from the user's settings.
});
