/* Copyright 2024 Marimo. All rights reserved. */

import {
  type CodeMirror,
  type CodeMirrorV,
  getCM,
  Vim,
} from "@replit/codemirror-vim";
import { type EditorView, keymap, ViewPlugin } from "@codemirror/view";
import {
  isAtEndOfEditor,
  isAtStartOfEditor,
  isInVimNormalMode,
} from "../utils";
import { invariant } from "@/utils/invariant";
import type { Extension } from "@codemirror/state";
import { Logger } from "@/utils/Logger";
import { goToDefinitionAtCursorPosition } from "../go-to-definition/utils";
import { once } from "@/utils/once";
import { onIdle } from "@/utils/idle";
import { cellActionsState, cellIdState } from "../cells/state";
import { sendFileDetails } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { resolvedMarimoConfigAtom } from "@/core/config/config";
import { parseVimrc, type VimCommand } from "./vimrc";

export function vimKeymapExtension(): Extension[] {
  addCustomVimCommandsOnce();
  loadVimrcOnce();

  return [
    keymap.of([
      {
        key: "j",
        run: (ev) => {
          if (isAtEndOfEditor(ev, true) && isInVimNormalMode(ev)) {
            const actions = ev.state.facet(cellActionsState);
            const cellId = ev.state.facet(cellIdState);
            actions.moveToNextCell({ cellId, before: false, noCreate: true });
            return true;
          }
          return false;
        },
      },
    ]),
    keymap.of([
      {
        key: "k",
        run: (ev) => {
          if (isAtStartOfEditor(ev) && isInVimNormalMode(ev)) {
            const actions = ev.state.facet(cellActionsState);
            const cellId = ev.state.facet(cellIdState);
            actions.moveToNextCell({ cellId, before: true, noCreate: true });
            return true;
          }
          return false;
        },
      },
    ]),
    keymap.of([
      {
        // Ctrl-[ by default is to dedent
        // But for Vim (on Linux), it should exit insert mode when in Insert mode
        linux: "Ctrl-[",
        run: (ev) => {
          const cm = getCM(ev);
          if (!cm) {
            Logger.warn(
              "Expected CodeMirror instance to have CodeMirror instance state",
            );
            return false;
          }
          if (!hasVimState(cm)) {
            Logger.warn("Expected CodeMirror instance to have Vim state");
            return false;
          }
          const vim = cm.state.vim;
          if (vim.insertMode) {
            Vim.exitInsertMode(cm, true);
            return true;
          }
          return false;
        },
      },
    ]),
    ViewPlugin.define((view) => {
      // Wait for the next animation frame so the CodeMirror instance is ready
      requestAnimationFrame(() => {
        CodeMirrorVimSync.INSTANCES.addInstance(view);
      });
      return {
        destroy() {
          CodeMirrorVimSync.INSTANCES.removeInstance(view);
        },
      };
    }),
  ];
}

const addCustomVimCommandsOnce = once(() => {
  // Go to definition
  Vim.defineAction("goToDefinition", (cm: CodeMirror) => {
    const view = cm.cm6;
    return goToDefinitionAtCursorPosition(view);
  });
  Vim.mapCommand("gd", "action", "goToDefinition", {}, { context: "normal" });

  // Save command
  Vim.defineEx("write", "w", (cm: CodeMirror) => {
    const view = cm.cm6;
    if (view) {
      const actions = view.state.facet(cellActionsState);
      actions.saveNotebook();
    }
  });
});

const loadVimrcOnce = once(async () => {
  const config = store.get(resolvedMarimoConfigAtom);
  const vimrc = config.keymap?.vimrc;
  if (!vimrc) {
    return;
  }

  try {
    Logger.log(`Loading vimrc from ${vimrc}`);
    const response = await sendFileDetails({ path: vimrc });
    const content = response.contents;
    if (!content) {
      Logger.error(`Failed to load vimrc from ${vimrc}`);
      return;
    }
    const vimCommands = parseVimrc(content, Logger.warn);
    applyVimCommands(vimCommands);
  } catch (error) {
    Logger.error("Failed to load vimrc:", error);
  }
});

function applyVimCommands(vimCommands: VimCommand[]) {
  // map, noremap and unmap can be used without ctx.
  // It is an important behavior that we want to use.

  function map(command: VimCommand) {
    if (!command.args) {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: expected aruments"`,
      );
      return;
    }
    if (!command.args.lhs || !command.args.rhs) {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: expected aruments"`,
      );
      return;
    }
    if (command.mode) {
      Vim.map(command.args.lhs, command.args.rhs, command.mode);
    } else {
      //@ts-expect-error We can use this without providing context (mode)
      Vim.map(command.args.lhs, command.args.rhs);
    }
  }

  function noremap(command: VimCommand) {
    if (!command.args) {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: expected aruments"`,
      );
      return;
    }
    if (!command.args.lhs || !command.args.rhs) {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: expected aruments"`,
      );
      return;
    }
    if (command.mode) {
      Vim.noremap(command.args.lhs, command.args.rhs, command.mode);
    } else {
      //@ts-expect-error We can use this without providing context (mode)
      Vim.noremap(command.args.lhs, command.args.rhs);
    }
  }

  function unmap(command: VimCommand) {
    if (!command.args) {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: expected aruments"`,
      );
      return;
    }
    if (!command.args.lhs) {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: expected aruments"`,
      );
      return;
    }
    if (command.mode) {
      Vim.unmap(command.args.lhs, command.mode);
    } else {
      //@ts-expect-error We can use this without providing context (mode)
      Vim.unmap(command.args.lhs);
    }
  }

  function mapclear(command: VimCommand) {
    if (command.mode) {
      Vim.mapclear(command.mode);
    } else {
      Vim.mapclear();
    }
  }

  for (const command of vimCommands) {
    if ("map|nmap|vmap|imap".split("|").includes(command.name)) {
      map(command);
    } else if (
      "noremap|nnoremap|vnoremap|inoremap".split("|").includes(command.name)
    ) {
      noremap(command);
    } else if ("unmap|nunmap|vunmap|iunmap".split("|").includes(command.name)) {
      unmap(command);
    } else if (
      "mapclear|nmapclear|vmapclear|imapclear".split("|").includes(command.name)
    ) {
      mapclear(command);
    } else {
      Logger.warn(
        `Could not execute vimrc command "${command.name}: unknown command"`,
      );
    }
  }
}

class CodeMirrorVimSync {
  private instances = new Set<EditorView>();
  private isBroadcasting = false;

  public static INSTANCES: CodeMirrorVimSync = new CodeMirrorVimSync();

  private constructor() {
    // noop
  }

  addInstance(instance: EditorView) {
    this.instances.add(instance);

    const cm = getCM(instance);
    if (!cm) {
      Logger.warn(
        "Expected CodeMirror instance to have CodeMirror instance state",
      );
      return;
    }

    // Create an event listener for Vim mode changes
    // When it changes, we broadcast it to all other CodeMirror instances
    cm.on("vim-mode-change", (e: { mode: string; subMode?: string }) => {
      if (this.isBroadcasting) {
        return;
      }
      invariant("mode" in e, 'Expected event to have a "mode" property');
      this.isBroadcasting = true;
      // We use onIdle to keep the focused editor snappy
      onIdle(() => {
        this.broadcastModeChange(instance, e.mode, e.subMode);
        this.isBroadcasting = false;
      });
    });
  }

  removeInstance(instance: EditorView) {
    this.instances.delete(instance);
  }

  broadcastModeChange(
    originInstance: EditorView,
    mode: string,
    subMode?: string,
  ) {
    invariant(
      "exitInsertMode" in Vim,
      "Vim does not have an exitInsertMode method",
    );
    invariant(
      "exitVisualMode" in Vim,
      "Vim does not have an exitVisualMode method",
    );

    for (const instance of this.instances) {
      if (instance !== originInstance) {
        const cm = getCM(instance);
        if (!cm) {
          Logger.warn(
            "Expected CodeMirror instance to have CodeMirror instance state",
          );
          continue;
        }

        // HACK: setSelections will steal focus from the current editor
        // so we remove it and set it back afterwards
        const prevSetSelections = cm.setSelections.bind(cm);
        cm.setSelections = () => {
          // noop
          return [];
        };

        if (!hasVimState(cm)) {
          Logger.warn("Expected CodeMirror instance to have Vim state");
          continue;
        }
        const vim = cm.state.vim;

        switch (mode) {
          case "normal":
            // Only exit insert mode if we're in it
            if (vim.insertMode) {
              Vim.exitInsertMode(cm, true);
            }
            // Only exit visual mode if we're in it
            if (vim.visualMode) {
              Vim.exitVisualMode(cm, true);
            }
            break;
          case "insert":
            // Only enter insert mode if we're not already in it
            if (!vim.insertMode) {
              Vim.handleKey(cm, "i", "");
            }
            break;
          case "visual":
            // We don't switch to visual mode across instances
            break;
        }

        // HACK: restore selection
        cm.setSelections = prevSetSelections;
      }
    }
  }
}

function hasVimState(cm: CodeMirror): cm is CodeMirrorV {
  return cm.state.vim !== undefined;
}
