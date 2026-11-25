/* Copyright 2026 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import { StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { createSharedResource } from "@/utils/shared-resource";
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

// Only editors with an underline need notification when a modifier is released.
const activeUnderlines = new Set<() => void>();
function resetModifier() {
  for (const clear of activeUnderlines) {
    clear();
  }
}
function trackModifier(event: KeyboardEvent) {
  if (!event.metaKey && !event.ctrlKey) {
    resetModifier();
  }
}
const subscribeToModifiers = createSharedResource(() => {
  window.addEventListener("keydown", trackModifier);
  window.addEventListener("keyup", trackModifier);
  window.addEventListener("blur", resetModifier);
  window.addEventListener("mouseleave", resetModifier);
  return () => {
    window.removeEventListener("keydown", trackModifier);
    window.removeEventListener("keyup", trackModifier);
    window.removeEventListener("blur", resetModifier);
    window.removeEventListener("mouseleave", resetModifier);
    resetModifier();
  };
});

// When meta is pressed, underline the variable name under the cursor
class MetaUnderlineVariablePlugin {
  private view: EditorView;
  private unsubscribeModifiers: () => void;
  private hoveredRange: { from: number; to: number; position: number } | null;
  private onClick: (view: EditorView) => void;

  public constructor(view: EditorView, onClick: (view: EditorView) => void) {
    this.view = view;
    this.hoveredRange = null;
    this.onClick = onClick;

    this.unsubscribeModifiers = subscribeToModifiers();
    this.view.dom.addEventListener("mousemove", this.mousemove);
    this.view.dom.addEventListener("click", this.click);
  }

  public update(_update: ViewUpdate) {
    // We cannot add any transactions here (e.g. clearing underlines),
    // otherwise CM fails with
    // "Calls to EditorView.update are not allowed while an update is in progress"
  }

  public destroy() {
    activeUnderlines.delete(this.clearUnderline);
    this.unsubscribeModifiers();
    this.view.dom.removeEventListener("mousemove", this.mousemove);
    this.view.dom.removeEventListener("click", this.click);
  }

  // While moving the mouse in cmd+click mode,
  // Track the variables we are hovering
  private mousemove = (event: MouseEvent) => {
    // Check if the key is still pressed
    if (!event.metaKey && !event.ctrlKey) {
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
      activeUnderlines.add(this.clearUnderline);
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
      activeUnderlines.add(this.clearUnderline);
      this.hoveredRange = { from, to, position: pos };
      this.view.dispatch({ effects: addUnderline.of(this.hoveredRange) });
    } else {
      this.clearUnderline();
    }
  };

  // If we have a hovered range, go to it
  private click = (event: MouseEvent) => {
    if (this.hoveredRange && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      event.stopPropagation();
      // Move the cursor before resolving so LSP uses the clicked position.
      this.view.dispatch({
        selection: {
          head: this.hoveredRange.position,
          anchor: this.hoveredRange.position,
        },
      });
      this.onClick(this.view);
    }
  };

  // Only clear the underline if we have some underline
  private clearUnderline = () => {
    activeUnderlines.delete(this.clearUnderline);
    if (this.hoveredRange) {
      this.view.dispatch({ effects: removeUnderlines.of(null) });
      this.hoveredRange = null;
    }
  };
}

export const createUnderlinePlugin = (onClick: (view: EditorView) => void) =>
  ViewPlugin.define((view) => new MetaUnderlineVariablePlugin(view, onClick));
