/* Copyright 2024 Marimo. All rights reserved. */

import { StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { type DebouncedFunc, debounce } from "lodash-es";

import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import { Logger } from "@/utils/Logger";

import { findReactiveVariables, type ReactiveVariableRange } from "./analyzer";

const reactiveVariableDecoration = Decoration.mark({
  class: "cm-reactive-variable",
});

const updateReactiveVariables = StateEffect.define<ReactiveVariableRange[]>();

/**
 * Plugin that manages highlighting marimo's reactive variables
 */
class ReactiveVariablesPlugin {
  private view: EditorView;
  private cellId: CellId;
  private variablesUnsubscribe: () => void;

  // Delay (in ms) before highlighting reactive variables after user changes or store updates
  private readonly highlightDebounceMs = 300;

  // Debounced function to trigger highlighting
  private readonly scheduleHighlighting: DebouncedFunc<() => void>;

  constructor(view: EditorView, cellId: CellId) {
    this.view = view;
    this.cellId = cellId;

    this.scheduleHighlighting = debounce(() => {
      this.runHighlighting();
    }, this.highlightDebounceMs);

    // React to variable store changes
    this.variablesUnsubscribe = store.sub(variablesAtom, () => {
      this.scheduleHighlighting();
    });

    // Initial run
    this.scheduleHighlighting();
  }

  update(update: ViewUpdate) {
    if (update.docChanged || update.focusChanged) {
      this.scheduleHighlighting();
    }
  }

  destroy() {
    this.scheduleHighlighting.cancel();
    this.variablesUnsubscribe();
  }

  private runHighlighting() {
    const ranges = findReactiveVariables({
      state: this.view.state,
      cellId: this.cellId,
      variables: store.get(variablesAtom),
    });

    if (ranges.length > 0) {
      Logger.debug(
        `Found ${ranges.length} reactive variables in cell ${this.cellId}`,
      );
    }

    // Defer dispatch to avoid triggering during an editor update cycle
    queueMicrotask(() => {
      this.view.dispatch({
        effects: updateReactiveVariables.of(ranges),
      });
    });
  }
}

/**
 * Creates the reactive variables extension
 */
export function reactiveVariablesExtension(cellId: CellId) {
  return [
    StateField.define<DecorationSet>({
      create() {
        return Decoration.none;
      },
      update(decorations, tr) {
        let newDecorations = decorations.map(tr.changes);
        for (const effect of tr.effects) {
          if (effect.is(updateReactiveVariables)) {
            // Replace all decorations with new ones
            newDecorations = Decoration.set(
              effect.value.map((range) =>
                reactiveVariableDecoration.range(range.from, range.to),
              ),
            );
          }
        }
        return newDecorations;
      },
      provide: (f) => EditorView.decorations.from(f),
    }),
    ViewPlugin.define((view) => new ReactiveVariablesPlugin(view, cellId)),
  ];
}
