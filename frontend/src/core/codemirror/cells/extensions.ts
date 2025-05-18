/* Copyright 2024 Marimo. All rights reserved. */
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { EditorView, type KeyBinding, keymap } from "@codemirror/view";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { type Extension, Prec } from "@codemirror/state";
import { formatKeymapExtension } from "../extensions";
import { getEditorCodeAsPython } from "../language/utils";
import { formattingChangeEffect } from "../format";
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import { isAtEndOfEditor, isAtStartOfEditor } from "../utils";
import { goToDefinitionAtCursorPosition } from "../go-to-definition/utils";
import {
  cellActionsState,
  cellIdState,
  type CodemirrorCellActions,
} from "./state";
import { createTracebackInfoAtom, SCRATCH_CELL_ID } from "@/core/cells/cells";
import { errorLineHighlighter } from "./traceback-decorations";
import { createObservable } from "@/core/state/observable";
import { store } from "@/core/state/jotai";

/**
 * Extensions for cell actions
 */
function cellKeymaps(cellId: CellId, hotkeys: HotkeyProvider): Extension[] {
  const keybindings: KeyBinding[] = [];

  keybindings.push(
    {
      key: hotkeys.getHotkey("cell.run").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const actions = ev.state.facet(cellActionsState);
        actions.onRun();
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.runAndNewBelow").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const actions = ev.state.facet(cellActionsState);
        actions.onRun();
        if (cellId === SCRATCH_CELL_ID) {
          return true;
        }
        ev.contentDOM.blur();
        actions.moveToNextCell({ cellId, before: false });
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.runAndNewAbove").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const actions = ev.state.facet(cellActionsState);
        actions.onRun();
        if (cellId === SCRATCH_CELL_ID) {
          return true;
        }
        ev.contentDOM.blur();
        actions.moveToNextCell({ cellId, before: true });
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.aiCompletion").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const actions = ev.state.facet(cellActionsState);
        const closed = actions.aiCellCompletion();
        if (closed) {
          ev.contentDOM.focus();
        }
        return true;
      },
    },
  );

  if (cellId !== SCRATCH_CELL_ID) {
    keybindings.push(
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
        key: hotkeys.getHotkey("cell.delete").key,
        preventDefault: true,
        stopPropagation: true,
        run: (cm) => {
          // Cannot delete non-empty cells for safety
          if (cm.state.doc.length === 0) {
            const actions = cm.state.facet(cellActionsState);
            actions.deleteCell();
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
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.moveCell({ cellId, before: true });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.moveDown").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.moveCell({ cellId, before: false });
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
            const actions = ev.state.facet(cellActionsState);
            actions.moveToNextCell({ cellId, before: true, noCreate: true });
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
            const actions = ev.state.facet(cellActionsState);
            actions.moveToNextCell({ cellId, before: false, noCreate: true });
            return true;
          }
          return false;
        },
      },
      {
        key: hotkeys.getHotkey("cell.focusDown").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.moveToNextCell({ cellId, before: false, noCreate: true });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.focusUp").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.moveToNextCell({ cellId, before: true, noCreate: true });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.sendToBottom").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.sendToBottom({ cellId });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.sendToTop").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.sendToTop({ cellId });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.createAbove").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          ev.contentDOM.blur();
          const actions = ev.state.facet(cellActionsState);
          actions.createNewCell({ cellId, before: true });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.createBelow").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          ev.contentDOM.blur();
          const actions = ev.state.facet(cellActionsState);
          actions.createNewCell({ cellId, before: false });
          return true;
        },
      },
      {
        key: hotkeys.getHotkey("cell.hideCode").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          const isHidden = actions.toggleHideCode();
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
        key: hotkeys.getHotkey("cell.splitCell").key,
        preventDefault: true,
        stopPropagation: true,
        run: (ev) => {
          const actions = ev.state.facet(cellActionsState);
          actions.splitCell({ cellId });
          if (!actions.moveToNextCell) {
            return true;
          }
          requestAnimationFrame(() => {
            ev.contentDOM.blur();
            actions.moveToNextCell({ cellId, before: false }); // focus new cell
          });
          return true;
        },
      },
    );
  }

  // Highest priority so that we can override the default keymap
  return [Prec.high(keymap.of(keybindings))];
}

/**
 * Extensions for cell code editing
 */
function cellCodeEditing(hotkeys: HotkeyProvider): Extension[] {
  const onChangePlugin = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      // Check if the doc update was a formatting change
      // e.g. changing from python to markdown
      const isFormattingChange = update.transactions.some((tr) =>
        tr.effects.some((effect) => effect.is(formattingChangeEffect)),
      );
      const nextCode = getEditorCodeAsPython(update.view);
      const cellActions = update.view.state.facet(cellActionsState);
      const cellId = update.view.state.facet(cellIdState);
      cellActions.updateCellCode({
        cellId,
        code: nextCode,
        formattingChange: isFormattingChange,
      });
    }
  });

  return [onChangePlugin, formatKeymapExtension(hotkeys)];
}

/**
 * Extension for auto-running markdown cells
 */
export function markdownAutoRunExtension({
  predicate,
}: {
  predicate: () => boolean;
}): Extension {
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

    if (!predicate()) {
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

    const actions = update.view.state.facet(cellActionsState);
    actions.onRun();
  });
}

export function cellBundle(
  cellId: CellId,
  hotkeys: HotkeyProvider,
  cellActions: CodemirrorCellActions,
): Extension[] {
  return [
    cellActionsState.of(cellActions),
    cellIdState.of(cellId),
    cellKeymaps(cellId, hotkeys),
    cellCodeEditing(hotkeys),
    errorLineHighlighter(
      createObservable(createTracebackInfoAtom(cellId), store),
    ),
  ];
}
