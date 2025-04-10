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

interface VimrcMapping {
  key: string;
  action: string;
  context: "normal" | "insert";
}

/**
 * Parses a vimrc file into a list of mappings
 *
 * @param content - The content of the vimrc file
 * @returns A list of mappings
 */
export function parseVimrc(content: string): VimrcMapping[] {
  const mappings: VimrcMapping[] = [];
  const lines = content.split("\n");

  for (const line of lines) {
    // Skip comments and empty lines
    if (line.startsWith('"') || line.trim() === "") {
      continue;
    }

    // Handle key mappings
    if (
      line.startsWith("map") ||
      line.startsWith("nmap") ||
      line.startsWith("imap")
    ) {
      const [, key, action] = line.split(/\s+/);
      if (!key || !action) {
        continue;
      }

      // Remove quotes if present
      const cleanKey = key.replaceAll(/["']/g, "");
      const cleanAction = action.replaceAll(/["']/g, "");

      mappings.push({
        key: cleanKey,
        action: cleanAction,
        context: line.startsWith("imap") ? "insert" : "normal",
      });
    }
  }

  return mappings;
}

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

    const mappings = parseVimrc(content);
    for (const mapping of mappings) {
      Vim.mapCommand(
        mapping.key,
        "action",
        mapping.action,
        {},
        { context: mapping.context },
      );
    }
  } catch (error) {
    Logger.error("Failed to load vimrc:", error);
  }
});

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
