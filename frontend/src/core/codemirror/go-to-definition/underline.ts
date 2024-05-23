/* Copyright 2024 Marimo. All rights reserved. */
import {
  EditorView,
  Decoration,
  type DecorationSet,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { StateField, StateEffect } from "@codemirror/state";
import { syntaxTree } from "@codemirror/language";
import type { TreeCursor } from "@lezer/common";

// Decoration
const underlineDecoration = Decoration.mark({ class: "underline" });

// State Effects
const addUnderline = StateEffect.define<{ from: number; to: number }>();
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
  private commandKey: boolean;
  private hoveredRange: { from: number; to: number; position: number } | null;
  private onClick: (view: EditorView, variableName: string) => void;

  constructor(
    view: EditorView,
    onClick: (view: EditorView, variableName: string) => void,
  ) {
    this.view = view;
    this.commandKey = false;
    this.hoveredRange = null;
    this.onClick = onClick;

    window.addEventListener("mousemove", this.mousemove);
    window.addEventListener("keydown", this.keydown);
    window.addEventListener("keyup", this.keyup);
    this.view.dom.addEventListener("click", this.click);
  }

  update(update: ViewUpdate) {
    if (update.docChanged || update.viewportChanged) {
      this.clearUnderline();
    }
  }

  destroy() {
    window.removeEventListener("mousemove", this.mousemove);
    window.removeEventListener("keydown", this.keydown);
    window.removeEventListener("keyup", this.keyup);
  }

  private mousemove = (event: MouseEvent) => {
    if (!this.commandKey) {
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
      this.clearUnderline();
      this.hoveredRange = { from, to, position: pos };
      this.view.dispatch({ effects: addUnderline.of(this.hoveredRange) });
    } else {
      this.clearUnderline();
    }
  };

  private keydown = (event: KeyboardEvent) => {
    if (event.key === "Meta" || event.key === "Ctrl") {
      this.commandKey = true;
    }
  };

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

  private keyup = (event: KeyboardEvent) => {
    if (event.key === "Meta" || event.key === "Ctrl") {
      this.commandKey = false;
      this.clearUnderline();
    }
  };

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
