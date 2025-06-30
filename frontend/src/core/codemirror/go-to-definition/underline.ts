/* Copyright 2024 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import { StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import type { TreeCursor } from "@lezer/common";
import {
  reactiveHoverDecoration,
  reactiveReferencesField,
} from "../reactive-references/extension";

// Decorations
const underlineDecoration = Decoration.mark({ class: "underline" });

// State Effects
const addUnderline = StateEffect.define<{ from: number; to: number }>();
const addReactiveHover = StateEffect.define<{ from: number; to: number }>();
const removeUnderlines = StateEffect.define();

// Underline Field
export const underlineField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none;
  },
  update(underlines, tr) {
    let newUnderlines = underlines.map(tr.changes);
    for (const effect of tr.effects) {
      if (effect.is(addUnderline)) {
        newUnderlines = underlines.update({
          add: [underlineDecoration.range(effect.value.from, effect.value.to)],
        });
      } else if (effect.is(addReactiveHover)) {
        newUnderlines = underlines.update({
          add: [
            reactiveHoverDecoration.range(effect.value.from, effect.value.to),
          ],
        });
      } else if (effect.is(removeUnderlines)) {
        newUnderlines = Decoration.none;
      }
    }
    return newUnderlines;
  },
  provide: (f) => EditorView.decorations.from(f),
});

// When meta is pressed, underline the variable name under the cursor
class MetaUnderlineVariablePlugin {
  private view: EditorView;
  private commandClickMode: boolean;
  private hoveredRange: { from: number; to: number; position: number } | null;
  private onClick: (view: EditorView, variableName: string) => void;

  constructor(
    view: EditorView,
    onClick: (view: EditorView, variableName: string) => void,
  ) {
    this.view = view;
    this.commandClickMode = false;
    this.hoveredRange = null;
    this.onClick = onClick;

    globalThis.addEventListener("keydown", this.keydown);
    globalThis.addEventListener("keyup", this.keyup);
    window.addEventListener("blur", this.windowBlur);
    globalThis.addEventListener("mouseleave", this.windowBlur);
  }

  update(_update: ViewUpdate) {
    // We cannot add any transactions here (e.g. clearing underlines),
    // otherwise CM fails with
    // "Calls to EditorView.update are not allowed while an update is in progress"
  }

  destroy() {
    globalThis.removeEventListener("keydown", this.keydown);
    globalThis.removeEventListener("keyup", this.keyup);
    window.removeEventListener("blur", this.windowBlur);
    globalThis.removeEventListener("mouseleave", this.windowBlur);
    this.view.dom.removeEventListener("mousemove", this.mousemove);
    this.view.dom.removeEventListener("click", this.click);
  }

  // Start the cmd+click mode
  private keydown = (event: KeyboardEvent) => {
    if (event.key === "Meta" || event.key === "Control") {
      this.commandClickMode = true;
      this.view.dom.addEventListener("mousemove", this.mousemove);
      this.view.dom.addEventListener("click", this.click);
    }
  };

  // Exit the cmd+click mode
  private keyup = (event: KeyboardEvent) => {
    if (event.key === "Meta" || event.key === "Control") {
      this.exitCommandClickMode();
    }
  };

  // Handle window blur event to reset state
  private windowBlur = () => {
    if (this.commandClickMode) {
      this.exitCommandClickMode();
    }
  };

  private exitCommandClickMode() {
    this.commandClickMode = false;
    this.view.dom.removeEventListener("mousemove", this.mousemove);
    this.view.dom.removeEventListener("click", this.click);
    this.clearUnderline();
  }

  // While moving the mouse in cmd+click mode,
  // Track the variables we are hovering
  private mousemove = (event: MouseEvent) => {
    // Check if the key is still pressed
    if (!event.metaKey && !event.ctrlKey) {
      this.exitCommandClickMode();
      return;
    }

    if (!this.commandClickMode) {
      this.clearUnderline();
      return;
    }

    const pos = this.view.posAtCoords({
      x: event.clientX,
      y: event.clientY,
    });
    if (pos == null) {
      this.clearUnderline();
      return;
    }

    // First, check if this position is a reactive variable (high-confidence navigable)
    // Use cached analysis from reactive variables StateField for fast lookup
    const reactiveState = this.view.state.field(reactiveReferencesField, false);
    const reactiveRange = reactiveState?.ranges.find(
      (range) => pos >= range.from && pos <= range.to,
    );

    if (reactiveRange) {
      // This is a reactive variable - add subtle hover enhancement
      const { from, to } = reactiveRange;
      if (
        this.hoveredRange &&
        this.hoveredRange.from === from &&
        this.hoveredRange.to === to
      ) {
        return;
      }
      // Clear existing decorations
      this.clearUnderline();
      // Add subtle hover enhancement for reactive variables
      this.hoveredRange = { from, to, position: pos };
      this.view.dispatch({ effects: addReactiveHover.of(this.hoveredRange) });
      return;
    }

    // Fallback: Use existing basic AST check for other variables
    const tree = syntaxTree(this.view.state);
    const cursor: TreeCursor = tree.cursorAt(pos);

    if (cursor.name === "VariableName") {
      const { from, to } = cursor;
      if (
        this.hoveredRange &&
        this.hoveredRange.from === from &&
        this.hoveredRange.to === to
      ) {
        return;
      }
      // Clear existing underlines
      this.clearUnderline();
      // Set the underline
      this.hoveredRange = { from, to, position: pos };
      this.view.dispatch({ effects: addUnderline.of(this.hoveredRange) });
    } else {
      this.clearUnderline();
    }
  };

  // If we have a hovered range, go to it
  private click = (event: MouseEvent) => {
    if (this.hoveredRange) {
      const variableName = this.view.state.doc.sliceString(
        this.hoveredRange.from,
        this.hoveredRange.to,
      );
      event.preventDefault();
      event.stopPropagation();
      this.onClick(this.view, variableName);
      // Move the cursor to the clicked position
      this.view.dispatch({
        selection: {
          head: this.hoveredRange.position,
          anchor: this.hoveredRange.position,
        },
      });
    }
  };

  // Only clear the underline if we have some underline
  private clearUnderline() {
    if (this.hoveredRange) {
      this.view.dispatch({ effects: removeUnderlines.of(null) });
      this.hoveredRange = null;
    }
  }
}

export const createUnderlinePlugin = (
  onClick: (view: EditorView, variableName: string) => void,
) =>
  ViewPlugin.define((view) => new MetaUnderlineVariablePlugin(view, onClick));
