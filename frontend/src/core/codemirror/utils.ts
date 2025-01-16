/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorState } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { getCM } from "@replit/codemirror-vim";

export function isAtStartOfEditor(ev: { state: EditorState }) {
  const main = ev.state.selection.main;
  return main.from === 0 && main.to === 0;
}

/**
 * Check if the cursor is at the end of the editor.
 *
 * If Vim is enabled, we also allow the second to last character to be selected,
 * since Vim's "normal" mode will select the last character.
 */
export function isAtEndOfEditor(ev: { state: EditorState }, isVim = false) {
  const main = ev.state.selection.main;
  const docLength = ev.state.doc.length;

  if (isVim && main.from === docLength - 1 && main.to === docLength - 1) {
    return true;
  }

  return main.from === docLength && main.to === docLength;
}

export function moveToEndOfEditor(ev: EditorView | undefined) {
  if (!ev) {
    return;
  }
  ev.dispatch({
    selection: {
      anchor: ev.state.doc.length,
      head: ev.state.doc.length,
    },
  });
}

export function isInVimNormalMode(ev: EditorView): boolean {
  const vimState = getCM(ev)?.state.vim;
  if (!vimState) {
    return false;
  }
  // If mode is not defined, check 'insertMode' and 'visualMode' instead
  if (!vimState.mode && !vimState.insertMode && !vimState.visualMode) {
    return true;
  }
  return vimState.mode === "normal";
}

export function selectAllText(ev: EditorView | undefined) {
  if (!ev) {
    return;
  }
  ev.dispatch({
    selection: {
      anchor: 0,
      head: ev.state.doc.length,
    },
  });
}
