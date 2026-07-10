/* Copyright 2026 Marimo. All rights reserved. */

import {
  type EditorState,
  type Extension,
  RangeSet,
  RangeSetBuilder,
  StateEffect,
  StateField,
} from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  gutter,
  GutterMarker,
  type PluginValue,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import type { CellId } from "@/core/cells/ids";
import type { Observable } from "@/core/state/observable";
import { Logger } from "@/utils/Logger";
import { toggleBreakpoint } from "./debugger-state";

// --- Current-line highlight -------------------------------------------------

function createLineDecoration(
  state: EditorState,
  line: number | null,
): DecorationSet {
  if (line == null || line < 1 || line > state.doc.lines) {
    return Decoration.none;
  }
  const builder = new RangeSetBuilder<Decoration>();
  try {
    const doc = state.doc.line(line);
    builder.add(
      doc.from,
      doc.from,
      Decoration.line({ class: "cm-debugger-current-line" }),
    );
  } catch (error) {
    Logger.debug("Invalid debugger line", { error });
  }
  return builder.finish();
}

class CurrentLineHighlighter implements PluginValue {
  private unsubscribe: () => void;
  decorations: DecorationSet;

  constructor(view: EditorView, lineObservable: Observable<number | null>) {
    this.decorations = createLineDecoration(view.state, lineObservable.get());
    this.unsubscribe = lineObservable.sub((line) => {
      this.decorations = createLineDecoration(view.state, line);
      // Force a re-render; the decoration set changed out of band.
      view.dispatch({ userEvent: "marimo.debugger-line-update" });
    });
  }

  update(update: ViewUpdate) {
    this.decorations = this.decorations.map(update.changes);
  }

  destroy() {
    this.unsubscribe();
  }
}

/** Highlight the line a cell's frame watcher is currently executing. */
export function debuggerLineHighlighter(
  lineObservable: Observable<number | null>,
): Extension {
  return [
    ViewPlugin.define(
      (view) => new CurrentLineHighlighter(view, lineObservable),
      { decorations: (plugin) => plugin.decorations },
    ),
    EditorView.theme({
      ".cm-debugger-current-line": {
        backgroundColor: "color-mix(in srgb, var(--amber-4) 50%, transparent)",
      },
    }),
  ];
}

// --- Breakpoint gutter ------------------------------------------------------

class BreakpointMarker extends GutterMarker {
  override toDOM() {
    const dot = document.createElement("div");
    dot.className = "cm-breakpoint-marker";
    return dot;
  }
}

const breakpointMarker = new BreakpointMarker();

const setBreakpointLines = StateEffect.define<ReadonlySet<number>>();

const breakpointLinesField = StateField.define<ReadonlySet<number>>({
  create: () => new Set<number>(),
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setBreakpointLines)) {
        return effect.value;
      }
    }
    return value;
  },
});

function buildBreakpointMarkers(state: EditorState): RangeSet<GutterMarker> {
  const lines = state.field(breakpointLinesField);
  if (lines.size === 0) {
    return RangeSet.empty;
  }
  const builder = new RangeSetBuilder<GutterMarker>();
  for (const lineNo of [...lines].toSorted((a, b) => a - b)) {
    if (lineNo >= 1 && lineNo <= state.doc.lines) {
      const line = state.doc.line(lineNo);
      builder.add(line.from, line.from, breakpointMarker);
    }
  }
  return builder.finish();
}

/** Keep `breakpointLinesField` in sync with the per-cell breakpoints atom. */
class BreakpointSync implements PluginValue {
  private unsubscribe: () => void;

  constructor(view: EditorView, observable: Observable<ReadonlySet<number>>) {
    const apply = (lines: ReadonlySet<number>) => {
      view.dispatch({ effects: setBreakpointLines.of(lines) });
    };
    // Dispatching during view construction is disallowed; defer the initial
    // sync (e.g. for editors that mount after breakpoints already exist).
    // Read the value fresh inside the microtask so a `sub` update that lands
    // first isn't clobbered by a stale snapshot.
    if (observable.get().size > 0) {
      queueMicrotask(() => apply(observable.get()));
    }
    this.unsubscribe = observable.sub(apply);
  }

  destroy() {
    this.unsubscribe();
  }
}

/** A clickable gutter for toggling breakpoints on a cell's lines. */
export function breakpointGutter(
  cellId: CellId,
  breakpointsObservable: Observable<ReadonlySet<number>>,
): Extension {
  return [
    breakpointLinesField,
    ViewPlugin.define(
      (view) => new BreakpointSync(view, breakpointsObservable),
    ),
    gutter({
      class: "cm-breakpoint-gutter",
      markers: (view) => buildBreakpointMarkers(view.state),
      initialSpacer: () => breakpointMarker,
      domEventHandlers: {
        mousedown: (view, line) => {
          const lineNo = view.state.doc.lineAt(line.from).number;
          toggleBreakpoint(cellId, lineNo);
          return true;
        },
      },
    }),
    EditorView.theme({
      ".cm-breakpoint-gutter": {
        width: "14px",
        cursor: "pointer",
      },
      ".cm-breakpoint-marker": {
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        backgroundColor: "var(--red-9)",
        margin: "4px auto",
      },
    }),
  ];
}
