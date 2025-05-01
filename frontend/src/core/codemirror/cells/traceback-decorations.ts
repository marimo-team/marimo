/* Copyright 2024 Marimo. All rights reserved. */
import {
  Decoration,
  type DecorationSet,
  EditorView,
  type PluginValue,
  ViewPlugin,
} from "@codemirror/view";
import {
  StateField,
  StateEffect,
  type Extension,
  type EditorState,
} from "@codemirror/state";
import { RangeSetBuilder } from "@codemirror/state";
import type { Observable } from "@/core/state/observable";
import type { TracebackInfo } from "@/utils/traceback";
import { cellIdState } from "./state";

type TracebackInfos = TracebackInfo[] | undefined;

/**
 * An effect to add errors.
 */
const addErrorEffect = StateEffect.define<TracebackInfos>();
/**
 * An effect to clear errors.
 */
const clearErrorsEffect = StateEffect.define();

/**
 * A state field to store the errors.
 */
const errorStateField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none;
  },
  update(decorations, tr) {
    let newDecorations = decorations.map(tr.changes);
    for (const effect of tr.effects) {
      if (effect.is(addErrorEffect)) {
        newDecorations = createErrorDecorations(tr.state, effect.value);
      }
      if (effect.is(clearErrorsEffect)) {
        newDecorations = Decoration.none;
      }
    }
    return newDecorations;
  },
  provide: (f) => EditorView.decorations.from(f),
});

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

  constructor(view: EditorView, errorsObservable: Observable<TracebackInfos>) {
    this.unsubscribe = errorsObservable.sub((errors) => {
      view.dispatch({ effects: addErrorEffect.of(errors) });
    });
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
  );
}

/**
 * Create an extension that highlights error lines in the editor.
 */
export function errorLineHighlighter(
  errorsObservable: Observable<TracebackInfos>,
): Extension {
  return [
    errorStateField,
    createErrorHighlighter(errorsObservable),
    EditorView.theme({
      ".cm-error-line": {
        backgroundColor: "var(--red-3)",
      },
      ".cm-error-line.cm-activeLine": {
        backgroundColor: "var(--red-4)",
      },
    }),
  ];
}
