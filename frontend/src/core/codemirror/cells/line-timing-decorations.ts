/* Copyright 2026 Marimo. All rights reserved. */

import {
  type EditorState,
  type Extension,
  RangeSetBuilder,
} from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  type PluginValue,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
} from "@codemirror/view";
import type { Observable } from "@/core/state/observable";
import { Logger } from "@/utils/Logger";
import { formatElapsedTime } from "@/utils/time";

/** The line a cell is currently executing and when execution first hit it. */
export interface ActiveLineInfo {
  line: number;
  startedAtMs: number;
}

// Only show the timer once a line has been busy this long, so short-lived
// lines never flash a pill.
const SHOW_TIMER_AFTER_MS = 500;
const TICK_INTERVAL_MS = 250;

/**
 * End-of-line elapsed-time pill for the currently executing line.
 *
 * Ticking is pure DOM mutation on the widget's own interval; no editor
 * transactions are dispatched while the timer counts.
 */
class LineTimerWidget extends WidgetType {
  // Track intervals per DOM node: CodeMirror may reuse the node across
  // decoration remaps (`eq` below), and `destroy` only receives the node.
  private static readonly intervals = new WeakMap<HTMLElement, number>();

  private readonly startedAtMs: number;

  constructor(startedAtMs: number) {
    super();
    this.startedAtMs = startedAtMs;
  }

  override eq(other: LineTimerWidget): boolean {
    return other.startedAtMs === this.startedAtMs;
  }

  override toDOM(): HTMLElement {
    const el = document.createElement("span");
    el.className = "cm-line-timer";
    el.setAttribute("aria-hidden", "true");
    const tick = () => {
      const elapsed = Date.now() - this.startedAtMs;
      el.textContent =
        elapsed >= SHOW_TIMER_AFTER_MS ? formatElapsedTime(elapsed) : "";
    };
    tick();
    LineTimerWidget.intervals.set(
      el,
      window.setInterval(tick, TICK_INTERVAL_MS),
    );
    return el;
  }

  override destroy(dom: HTMLElement): void {
    const interval = LineTimerWidget.intervals.get(dom);
    if (interval !== undefined) {
      window.clearInterval(interval);
      LineTimerWidget.intervals.delete(dom);
    }
  }

  override ignoreEvent(): boolean {
    return true;
  }
}

function createTimingDecorations(
  state: EditorState,
  info: ActiveLineInfo | null,
): DecorationSet {
  if (info === null || info.line < 1 || info.line > state.doc.lines) {
    return Decoration.none;
  }
  const builder = new RangeSetBuilder<Decoration>();
  try {
    const line = state.doc.line(info.line);
    builder.add(
      line.from,
      line.from,
      Decoration.line({ class: "cm-timing-current-line" }),
    );
    builder.add(
      line.to,
      line.to,
      Decoration.widget({
        widget: new LineTimerWidget(info.startedAtMs),
        side: 1,
      }),
    );
  } catch (error) {
    Logger.debug("Invalid timing line", { error });
  }
  return builder.finish();
}

class ActiveLineTimer implements PluginValue {
  private unsubscribe: () => void;
  decorations: DecorationSet;

  constructor(
    view: EditorView,
    infoObservable: Observable<ActiveLineInfo | null>,
  ) {
    this.decorations = createTimingDecorations(
      view.state,
      infoObservable.get(),
    );
    this.unsubscribe = infoObservable.sub((info) => {
      this.decorations = createTimingDecorations(view.state, info);
      // Force a re-render; the decoration set changed out of band.
      view.dispatch({ userEvent: "marimo.timing-line-update" });
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
 * Highlight the line a cell's frame watcher is currently executing in green,
 * with a dim elapsed-time pill at the end of the line once it has been busy
 * for a while.
 */
export function activeLineTimer(
  infoObservable: Observable<ActiveLineInfo | null>,
): Extension {
  return [
    ViewPlugin.define((view) => new ActiveLineTimer(view, infoObservable), {
      decorations: (plugin) => plugin.decorations,
    }),
    EditorView.theme({
      ".cm-timing-current-line": {
        backgroundColor: "color-mix(in srgb, var(--grass-4) 50%, transparent)",
      },
      ".cm-line-timer": {
        color: "var(--grass-11)",
        fontSize: "0.85em",
        marginLeft: "1.5ch",
        pointerEvents: "none",
      },
    }),
  ];
}
