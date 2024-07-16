/* Copyright 2024 Marimo. All rights reserved. */

import { getCM, Vim } from "@replit/codemirror-vim";
import { type EditorView, keymap, ViewPlugin } from "@codemirror/view";
import {
  isAtEndOfEditor,
  isAtStartOfEditor,
  isInVimNormalMode,
} from "../utils";
import { invariant } from "@/utils/invariant";
import type { Extension } from "@codemirror/state";

console.log(Vim);
invariant(
  "exitInsertMode" in Vim,
  "Vim does not have an exitInsertMode method",
);
// invariant(
// 	"enterInsertMode" in Vim,
// 	"Vim does not have an enterInsertMode method",
// );
// invariant(
// 	"enterVisualMode" in Vim,
// 	"Vim does not have an enterVisualMode method",
// );
invariant(
  "exitVisualMode" in Vim,
  "Vim does not have an exitVisualMode method",
);

export function vimKeymapExtension(callbacks: {
  focusUp: () => void;
  focusDown: () => void;
}): Extension[] {
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
      console.log(view);
      CodeMirrorSync.INSTANCES.addInstance(view);
      return {
        destroy() {
          CodeMirrorSync.INSTANCES.removeInstance(view);
        },
      };
    }),
  ];
}

class CodeMirrorSync {
  private instances = new Set<EditorView>();
  private isBroadcasting = false;

  public static INSTANCES: CodeMirrorSync = new CodeMirrorSync();

  private constructor() {
    // noop
  }

  addInstance(instance: EditorView) {
    console.log("addInstance", getCM(instance));
    getCM(instance)?.on("vim-mode-change", (e: { mode: string }) => {
      if (this.isBroadcasting) {
        return;
      }
      invariant("mode" in e, 'Expected event to have a "mode" property');
      console.log("mode changed");
      console.log(e);
      const mode = e.mode;
      this.isBroadcasting = true;
      // trap focus
      const handleTrapAllFocus = (e: FocusEvent) => {
        console.log("focaus");
        e.preventDefault();
      };
      const handleTrapScroll = (e: WheelEvent) => {
        e.preventDefault();
      };

      document.addEventListener("focus", handleTrapAllFocus, true);
      document.addEventListener("focusin", handleTrapAllFocus);
      document.addEventListener("focusout", handleTrapAllFocus);
      document.addEventListener("blur", handleTrapAllFocus);
      document.addEventListener("wheel", handleTrapScroll, { passive: false });
      const app = document.querySelector<HTMLElement>("#App");
      // get scroll of app
      const appScrollTop = app?.scrollTop ?? 0;
      console.log(appScrollTop);
      this.broadcastModeChange(instance, mode);
      // reset scroll
      app?.scrollTo(0, appScrollTop);
      console.log(appScrollTop);
      const cm = getCM(instance)?.focus();
      document.removeEventListener("focus", handleTrapAllFocus, true);
      document.removeEventListener("focusin", handleTrapAllFocus);
      document.removeEventListener("focusout", handleTrapAllFocus);
      document.removeEventListener("blur", handleTrapAllFocus);
      document.removeEventListener("wheel", handleTrapScroll);
      document.removeEventListener("wheel", handleTrapScroll);
      document.removeEventListener("focus", handleTrapAllFocus, true);
      // restore focus

      this.isBroadcasting = false;
    });
    this.instances.add(instance);
  }

  removeInstance(instance: EditorView) {
    this.instances.delete(instance);
  }

  broadcastModeChange(originInstance: EditorView, mode: string) {
    for (const instance of this.instances) {
      if (instance !== originInstance) {
        // const cm = getCM(instance);
        // cm.focus = () => {
        // 	// do nothing
        // 	console.log("focus");
        // };
        switch (mode) {
          case "normal":
            console.log("leaving vim mode");
            Vim.handleKey(getCM(instance), "<Esc>");
            break;
          case "insert":
            Vim.handleKey(getCM(instance), "i");
            break;
          case "visual":
            Vim.handleKey(getCM(instance), "v");
            break;
        }
      }
    }
  }
}
