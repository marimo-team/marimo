/* Copyright 2024 Marimo. All rights reserved. */
import {
  Decoration,
  type DecorationSet,
  EditorView,
  type PluginValue,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import type { Extension, EditorState } from "@codemirror/state";
import { RangeSetBuilder } from "@codemirror/state";
import type { Observable } from "@/core/state/observable";
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
    .filter((error) => error.cellId === cellId)
    .sort((a, b) => a.lineNumber - b.lineNumber);

  for (const error of relevantErrors) {
    const line = state.doc.line(error.lineNumber);
    const deco = Decoration.line({
      class: "cm-error-line",
    });
    builder.add(line.from, line.from, deco);
  }

  return builder.finish();
}

/**
 * A view plugin that highlights error lines in the editor.
 */
class ErrorHighlighter implements PluginValue {
  private unsubscribe: () => void;
  decorations: DecorationSet;

  constructor(view: EditorView, errorsObservable: Observable<TracebackInfos>) {
    this.decorations = createErrorDecorations(
      view.state,
      errorsObservable.get(),
    );

    this.unsubscribe = errorsObservable.sub((errors) => {
      this.decorations = createErrorDecorations(view.state, errors);
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
