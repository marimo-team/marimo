/* Copyright 2024 Marimo. All rights reserved. */
import { isPlatformMac } from "@/core/hotkeys/shortcuts";
import { Objects } from "@/utils/objects";

export const NOT_SET: unique symbol = Symbol("NOT_SET");

interface Hotkey {
  name: string;
  /**
   * Grouping for the command palette and keyboard shortcuts page.
   * If not specified, the command will not be shown in the command palette.
   */
  group: HotkeyGroup | undefined;
  key:
    | string
    | typeof NOT_SET
    | {
        main: string;
        /** macOS specific override */
        mac?: string;
        /** Windows specific override */
        windows?: string;
        /** Linux specific override */
        linux?: string;
      };
  /**
   * @default true
   */
  editable?: boolean;
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
  | "Markdown"
  | "Command"
  | "Other";

const DEFAULT_HOT_KEY = {
  // Cell Navigation
  "cell.focusUp": {
    name: "Go to previous cell",
    group: "Navigation",
    key: "Mod-Shift-k",
  },
  "cell.focusDown": {
    name: "Go to next cell",
    group: "Navigation",
    key: "Mod-Shift-j",
  },

  // Creation and Ordering
  "cell.moveUp": {
    name: "Move cell up",
    group: "Creation and Ordering",
    key: "Mod-Shift-9",
  },
  "cell.moveDown": {
    name: "Move cell down",
    group: "Creation and Ordering",
    key: "Mod-Shift-0",
  },
  "cell.moveLeft": {
    name: "Move left",
    group: "Creation and Ordering",
    key: "Mod-Shift-7",
  },
  "cell.moveRight": {
    name: "Move right",
    group: "Creation and Ordering",
    key: "Mod-Shift-8",
  },
  "cell.createAbove": {
    name: "New cell above",
    group: "Creation and Ordering",
    key: "Mod-Shift-o",
  },
  "cell.createBelow": {
    name: "New cell below",
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
  "cell.addColumnBreakpoint": {
    name: "Add column breakpoint",
    group: "Creation and Ordering",
    key: "Mod-Shift-3",
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
  "global.runAll": {
    name: "Re-run all cells",
    group: "Running Cells",
    key: NOT_SET,
  },

  // Editing Cells
  "cell.format": {
    name: "Format cell",
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
  "cell.signatureHelp": {
    name: "Signature help",
    group: "Editing",
    key: "Mod-Shift-Space",
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
    name: "Find and Replace",
    group: "Editing",
    key: "Mod-f",
  },
  "cell.selectNextOccurrence": {
    name: "Add selection to next Find match",
    group: "Editing",
    key: "Mod-d",
  },
  "cell.fold": {
    name: "Fold region",
    group: "Editing",
    key: {
      main: "Mod-Alt-[",
      windows: "Mod-Shift-[",
    },
  },
  "cell.unfold": {
    name: "Unfold region",
    group: "Editing",
    key: {
      main: "Mod-Alt-]",
      windows: "Mod-Shift-]",
    },
  },
  "cell.foldAll": {
    name: "Fold all regions",
    group: "Editing",
    key: "Ctrl-Alt-[",
  },
  "cell.unfoldAll": {
    name: "Unfold all regions",
    group: "Editing",
    key: "Ctrl-Alt-]",
  },
  "cell.delete": {
    name: "Delete cell",
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
  "cell.splitCell": {
    name: "Split cell",
    group: "Editing",
    key: "Mod-Shift-'",
  },
  "cell.toggleComment": {
    name: "Toggle comment",
    group: "Editing",
    // https://github.com/codemirror/commands/blob/6.8.1/src/commands.ts#L1067
    key: "Mod-/",
  },
  "cell.toggleBlockComment": {
    name: "Toggle block comment",
    group: "Editing",
    // https://github.com/codemirror/commands/blob/6.8.1/src/commands.ts#L1068
    key: "Alt-A",
  },
  "cell.renameSymbol": {
    name: "Rename symbol",
    group: "Editing",
    key: "F2",
  },

  // Markdown
  "markdown.bold": {
    name: "Bold",
    group: "Markdown",
    key: "Mod-b",
  },
  "markdown.italic": {
    name: "Italic",
    group: "Markdown",
    key: "Mod-i",
  },
  "markdown.link": {
    name: "Convert to Link",
    group: "Markdown",
    key: "Mod-k",
  },
  "markdown.orderedList": {
    name: "Convert to Ordered list",
    group: "Markdown",
    key: "Mod-Shift-7",
  },
  "markdown.unorderedList": {
    name: "Convert to Unordered list",
    group: "Markdown",
    key: "Mod-Shift-8",
  },
  "markdown.blockquote": {
    name: "Convert to Blockquote",
    group: "Markdown",
    key: "Mod-Shift-9",
  },
  "markdown.code": {
    name: "Convert to Code",
    group: "Markdown",
    key: "Mod-Shift-0",
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
    name: "Show keyboard shortcuts",
    group: "Other",
    key: "Mod-Shift-h",
  },
  "global.save": {
    name: "Save file",
    group: "Other",
    key: "Mod-s",
  },
  "global.commandPalette": {
    name: "Show command palette",
    group: "Other",
    key: "Mod-k",
  },
  "global.runStale": {
    name: "Run all stale cells",
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
  "global.toggleTerminal": {
    name: "Show integrated terminal",
    group: "Other",
    key: "Ctrl-`",
  },
  "global.collapseAllSections": {
    name: "Collapse all sections",
    group: "Editing",
    key: "Mod-Shift-\\",
  },
  "global.expandAllSections": {
    name: "Expand all sections",
    group: "Editing",
    key: "Mod-Shift-/",
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
  "cell.goToDefinition": {
    name: "Go to Definition",
    group: "Navigation",
    key: "F12",
  },
  "completion.moveDown": {
    name: "Move completion selection down",
    group: "Editing",
    key: "Ctrl-j",
  },
  "completion.moveUp": {
    name: "Move completion selection up",
    group: "Editing",
    key: "Ctrl-k",
  },

  // Command mode (edit a cell, not the editor)
  "command.createCellBefore": {
    name: "Create a cell before current cell",
    group: "Command",
    key: "a",
  },
  "command.createCellAfter": {
    name: "Create a cell after current cell",
    group: "Command",
    key: "b",
  },
  "command.copyCell": {
    name: "Copy cell",
    group: "Command",
    key: "c",
  },
  "command.pasteCell": {
    name: "Paste cell",
    group: "Command",
    key: "v",
  },
} satisfies Record<string, Hotkey>;

export type HotkeyAction = keyof typeof DEFAULT_HOT_KEY;

export function isHotkeyAction(x: string): x is HotkeyAction {
  return x in DEFAULT_HOT_KEY;
}

export function getDefaultHotkey(action: HotkeyAction): ResolvedHotkey {
  return new HotkeyProvider(DEFAULT_HOT_KEY).getHotkey(action);
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
    if (key === NOT_SET) {
      return {
        name,
        key: "",
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

  isEditable(action: HotkeyAction): boolean {
    return this.hotkeys[action].editable !== false;
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
