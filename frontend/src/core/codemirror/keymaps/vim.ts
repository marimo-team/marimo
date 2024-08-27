/* Copyright 2024 Marimo. All rights reserved. */

import { type CodeMirror, getCM, Vim } from "@replit/codemirror-vim";
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

export function vimKeymapExtension(callbacks: {
  focusUp: () => void;
  focusDown: () => void;
}): Extension[] {
  addCustomVimCommandsOnce();

  return [
    keymap.of([
      {
        key: "j",
        run: (ev) => {
          if (isAtEndOfEditor(ev, true) && isInVimNormalMode(ev)) {
            callbacks.focusDown();
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
            callbacks.focusUp();
            return true;
          }
          return false;
        },
      },
    ]),
    ViewPlugin.define((view) => {
      CodeMirrorVimSync.INSTANCES.addInstance(view);
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
    cm.on("vim-mode-change", (e: { mode: string }) => {
      if (this.isBroadcasting) {
        return;
      }
      invariant("mode" in e, 'Expected event to have a "mode" property');
      const mode = e.mode;
      this.isBroadcasting = true;
      this.broadcastModeChange(instance, mode);
      this.isBroadcasting = false;
    });
  }

  removeInstance(instance: EditorView) {
    this.instances.delete(instance);
  }

  broadcastModeChange(originInstance: EditorView, mode: string) {
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

        const vim = cm.state.vim;
        if (!vim) {
          Logger.warn("Expected CodeMirror instance to have Vim state");
          continue;
        }

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
