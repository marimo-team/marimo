/* Copyright 2024 Marimo. All rights reserved. */
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { EditorView, type KeyBinding, keymap } from "@codemirror/view";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { type Extension, Prec } from "@codemirror/state";
import { formatKeymapExtension } from "../extensions";
import type { CellActions } from "@/core/cells/cells";
import { getEditorCodeAsPython } from "../language/utils";
import { formattingChangeEffect } from "../format";
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import { isAtEndOfEditor, isAtStartOfEditor } from "../utils";
import { goToDefinitionAtCursorPosition } from "../go-to-definition/utils";

export interface MovementCallbacks
  extends Pick<CellActions, "splitCell" | "sendToTop" | "sendToBottom"> {
  moveToNextCell: CellActions["moveToNextCell"] | undefined;
  onRun: () => void;
  deleteCell: () => void;
  createAbove: () => void;
  createBelow: () => void;
  createManyBelow: (content: string[]) => void;
  moveUp: () => void;
  moveDown: () => void;
  focusUp: () => void;
  focusDown: () => void;
  toggleHideCode: () => boolean;
  aiCellCompletion: () => boolean;
}

/**
 * Extensions for cell movement
 */
export function cellMovementBundle(
  cellId: CellId,
  callbacks: MovementCallbacks,
  hotkeys: HotkeyProvider,
): Extension[] {
  const {
    onRun,
    deleteCell,
    createAbove,
    createBelow,
    moveUp,
    moveDown,
    focusUp,
    focusDown,
    sendToTop,
    sendToBottom,
    splitCell,
    moveToNextCell,
    toggleHideCode,
    aiCellCompletion,
  } = callbacks;

  const keybindings: KeyBinding[] = [
    {
      key: hotkeys.getHotkey("cell.run").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        onRun();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.runAndNewBelow").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        onRun();
        if (!moveToNextCell) {
          return true;
        }
        ev.contentDOM.blur();
        moveToNextCell({ cellId, before: false });
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.runAndNewAbove").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        onRun();
        if (!moveToNextCell) {
          return true;
        }
        ev.contentDOM.blur();
        moveToNextCell({ cellId, before: true });
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.delete").key,
      preventDefault: true,
      stopPropagation: true,
      run: (cm) => {
        // Cannot delete non-empty cells for safety
        if (cm.state.doc.length === 0) {
          deleteCell();
        }
        // shortcuts.delete (shift-backspace) overlaps with
        // defaultKeymap's deleteCharBackward (backspace); we don't want
        // shift-backspace to trigger character deletion, because otherwise
        // users might accidentally delete their whole notebook if they
        // absent-mindedly held these keys. That's why we always return true.
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.moveUp").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        moveUp();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.moveDown").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        moveDown();
        return true;
      },
    },
    {
      key: "ArrowUp",
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        // Skip if we are in the middle of an autocompletion
        const hasAutocomplete = completionStatus(ev.state);
        if (hasAutocomplete) {
          return false;
        }

        if (isAtStartOfEditor(ev)) {
          focusUp();
          return true;
        }
        return false;
      },
    },
    {
      key: "ArrowDown",
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        // Skip if we are in the middle of an autocompletion
        const hasAutocomplete = completionStatus(ev.state);
        if (hasAutocomplete) {
          return false;
        }

        if (isAtEndOfEditor(ev)) {
          focusDown();
          return true;
        }
        return false;
      },
    },
    {
      key: hotkeys.getHotkey("cell.focusDown").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        focusDown();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.focusUp").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        focusUp();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.sendToBottom").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        sendToBottom({ cellId });
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.sendToTop").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        sendToTop({ cellId });
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.createAbove").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        ev.contentDOM.blur();
        createAbove();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.createBelow").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        ev.contentDOM.blur();
        createBelow();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.hideCode").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const isHidden = toggleHideCode();
        closeCompletion(ev);
        // If we are newly hidden, blur the editor
        if (isHidden) {
          ev.contentDOM.blur();
          // Focus on the parent element
          // https://github.com/marimo-team/marimo/issues/2941
          document
            .getElementById(HTMLCellId.create(cellId))
            ?.parentElement?.focus();
        } else {
          ev.contentDOM.focus();
        }
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.aiCompletion").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const closed = aiCellCompletion();
        if (closed) {
          ev.contentDOM.focus();
        }
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.goToDefinition").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        goToDefinitionAtCursorPosition(ev);
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.splitCell").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        splitCell({ cellId });
        if (!moveToNextCell) {
          return true;
        }
        requestAnimationFrame(() => {
          ev.contentDOM.blur();
          moveToNextCell({ cellId, before: false }); // focus new cell
        });
        return true;
      },
    },
  ];

  // Highest priority so that we can override the default keymap
  return [Prec.high(keymap.of(keybindings))];
}

export interface CodeCallbacks {
  updateCellCode: CellActions["updateCellCode"];
  afterToggleMarkdown: () => void;
}

/**
 * Extensions for cell code editing
 */
export function cellCodeEditingBundle(
  cellId: CellId,
  callbacks: CodeCallbacks,
  hotkeys: HotkeyProvider,
): Extension[] {
  const { updateCellCode } = callbacks;

  const onChangePlugin = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      // Check if the doc update was a formatting change
      // e.g. changing from python to markdown
      const isFormattingChange = update.transactions.some((tr) =>
        tr.effects.some((effect) => effect.is(formattingChangeEffect)),
      );
      const nextCode = getEditorCodeAsPython(update.view);
      updateCellCode({
        cellId,
        code: nextCode,
        formattingChange: isFormattingChange,
      });
    }
  });

  return [onChangePlugin, formatKeymapExtension(cellId, callbacks, hotkeys)];
}

/**
 * Extension for auto-running markdown cells
 */
export function markdownAutoRunExtension(
  callbacks: MovementCallbacks,
): Extension {
  return EditorView.updateListener.of((update) => {
    // If the doc didn't change, ignore
    if (!update.docChanged) {
      return;
    }

    // If not focused, ignore
    // This can cause multiple runs when in RTC mode
    if (!update.view.hasFocus) {
      return;
    }

    // This happens on mount when we start in markdown mode
    const isFormattingChange = update.transactions.some((tr) =>
      tr.effects.some((effect) => effect.is(formattingChangeEffect)),
    );
    if (isFormattingChange) {
      // Ignore formatting changes
      return;
    }

    callbacks.onRun();
  });
}
