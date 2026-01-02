/* Copyright 2026 Marimo. All rights reserved. */

import { foldedRanges, unfoldEffect } from "@codemirror/language";
import type { EditorState, Extension, StateEffect } from "@codemirror/state";
import { RangeSetBuilder } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  type PluginValue,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import type { Observable } from "@/core/state/observable";
import { Logger } from "@/utils/Logger";
import type { TracebackInfo } from "@/utils/traceback";
import { cellIdState } from "./state";

type TracebackInfos = TracebackInfo[] | undefined;

/**
 * Create the decoration for error lines.
 */
function createErrorDecorations(state: EditorState, errors: TracebackInfos) {
  if (!errors?.length) {
    return Decoration.none;
  }

  const builder = new RangeSetBuilder<Decoration>();
  const cellId = state.facet(cellIdState);

  // Filter and sort errors by line number to ensure they're added in order
  const relevantErrors = errors
    .filter((error) => error.kind === "cell" && error.cellId === cellId)
    .sort((a, b) => a.lineNumber - b.lineNumber);

  for (const error of relevantErrors) {
    try {
      const line = state.doc.line(error.lineNumber);
      const deco = Decoration.line({
        class: "cm-error-line",
      });
      builder.add(line.from, line.from, deco);
    } catch (error) {
      Logger.debug("Invalid line number in error decoration", { error });
    }
  }

  return builder.finish();
}

/**
 * Unfolds any folded regions that contain error lines.
 */
function unfoldErrorLines(view: EditorView, errors: TracebackInfos) {
  if (!errors?.length) {
    return;
  }

  const cellId = view.state.facet(cellIdState);
  const relevantErrors = errors.filter(
    (error) => error.kind === "cell" && error.cellId === cellId,
  );

  if (relevantErrors.length === 0) {
    return;
  }

  const folded = foldedRanges(view.state);
  const effects: StateEffect<unknown>[] = [];

  for (const error of relevantErrors) {
    try {
      const line = view.state.doc.line(error.lineNumber);
      // Check if this line is inside a folded region
      folded.between(line.from, line.to, (from, to) => {
        effects.push(unfoldEffect.of({ from, to }));
      });
    } catch (error) {
      Logger.debug("Invalid line numbers", { error });
    }
  }

  if (effects.length > 0) {
    view.dispatch({ effects });
  }
}

/**
 * A view plugin that highlights error lines in the editor.
 */
class ErrorHighlighter implements PluginValue {
  private unsubscribe: () => void;
  decorations: DecorationSet;

  constructor(view: EditorView, errorsObservable: Observable<TracebackInfos>) {
    const errors = errorsObservable.get();
    this.decorations = createErrorDecorations(view.state, errors);
    unfoldErrorLines(view, errors);

    this.unsubscribe = errorsObservable.sub((errors) => {
      // Prev length
      const prevLength = this.decorations.size;
      this.decorations = createErrorDecorations(view.state, errors);
      unfoldErrorLines(view, errors);

      if (prevLength !== this.decorations.size) {
        // Force a re-render
        view.dispatch({
          userEvent: "marimo.error-decoration-update",
        });
      }
    });
  }

  update(update: ViewUpdate) {
    this.decorations = this.decorations.map(update.changes);
  }

  destroy() {
    this.unsubscribe();
  }
}

/**
 * Create a view plugin that highlights error lines in the editor.
 */
function createErrorHighlighter(errorsObservable: Observable<TracebackInfos>) {
  return ViewPlugin.define(
    (view) => new ErrorHighlighter(view, errorsObservable),
    {
      decorations: (f) => f.decorations,
    },
  );
}

/**
 * Create an extension that highlights error lines in the editor.
 */
export function errorLineHighlighter(
  errorsObservable: Observable<TracebackInfos>,
): Extension {
  return [
    createErrorHighlighter(errorsObservable),
    EditorView.theme({
      ".cm-error-line": {
        backgroundColor: "color-mix(in srgb, var(--red-4) 40%, transparent)",
      },
      "&.cm-focused .cm-error-line.cm-activeLine": {
        backgroundColor: "color-mix(in srgb, var(--red-6) 40%, transparent)",
      },
    }),
  ];
}
