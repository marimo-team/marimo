/* Copyright 2026 Marimo. All rights reserved. */

import type * as PlotlyTypes from "plotly.js";
// Import the pre-built dist bundle, not the source entry point.
// The source entry point requires Node.js polyfills (e.g. `buffer/`)
// that are unavailable in the browser/bundler environment.
// oxlint-disable-next-line typescript/ban-ts-comment
// @ts-expect-error — no type declarations for dist path, we use PlotlyTypes above
import Plotly from "plotly.js/dist/plotly";
import { useEffect, useRef } from "react";

// Plotly attaches `on` and `removeListener` to the DOM element at runtime.
// The @types/plotly.js PlotlyHTMLElement type includes `on` and `removeAllListeners`
// but not the per-handler `removeListener`. We extend the type to include it.
interface PlotlyElement extends PlotlyTypes.PlotlyHTMLElement {
  removeListener(event: string, handler: (...args: never[]) => void): void;
}

export interface Figure {
  data: PlotlyTypes.Data[];
  layout: Partial<PlotlyTypes.Layout>;
  frames: PlotlyTypes.Frame[] | null;
}

export interface SelectedPoint {
  curveNumber?: unknown;
  pointIndex?: unknown;
  pointNumber?: unknown;
}

export interface PlotProps {
  data: PlotlyTypes.Data[];
  layout: Partial<PlotlyTypes.Layout>;
  frames?: PlotlyTypes.Frame[];
  config?: Partial<PlotlyTypes.Config>;
  className?: string;
  style?: React.CSSProperties;
  useResizeHandler?: boolean;
  divId?: string;
  hasSelection?: boolean;
  selectedPoints?: ReadonlyArray<SelectedPoint>;
  layoutSelections?: ReadonlyArray<unknown>;
  onRelayout?: (event: PlotlyTypes.PlotRelayoutEvent) => void;
  onRelayouting?: (event: PlotlyTypes.PlotRelayoutEvent) => void;
  onSelected?: (event: PlotlyTypes.PlotSelectionEvent) => void;
  onDeselect?: () => void;
  onClick?: (event: PlotlyTypes.PlotMouseEvent) => void;
  onSunburstClick?: (event: PlotlyTypes.PlotMouseEvent) => void;
  onTreemapClick?: (event: PlotlyTypes.PlotMouseEvent) => void;
  onError?: (err: Error) => void;
}

// Plotly event name convention:
//   - events are attached as `'plotly_' + name.toLowerCase()`
//   - react props are `'on' + name`
const EVENT_NAMES = [
  "Relayout",
  "Relayouting",
  "Selected",
  "Deselect",
  "Click",
  "SunburstClick",
  "TreemapClick",
] as const;

type EventName = (typeof EVENT_NAMES)[number];

function propName(event: EventName): keyof PlotProps {
  return `on${event}` as keyof PlotProps;
}

function plotlyEventName(event: EventName): string {
  return `plotly_${event.toLowerCase()}`;
}

export const Plot = (props: PlotProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const {
    data,
    layout,
    config,
    frames,
    className,
    style,
    useResizeHandler,
    divId,
    onError,
  } = props;

  // Render / update the plot
  useEffect(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }

    Plotly.react(el, data, layout, config)
      .then(() => {
        if (frames && frames.length > 0) {
          return Plotly.addFrames(el as unknown as PlotlyTypes.Root, frames);
        }
      })
      .catch((error: Error) => {
        onError?.(error);
      });
  }, [data, layout, config, frames, onError]);

  // Sync event handlers
  useEffect(
    () => {
      const el = containerRef.current;
      if (!el) {
        return;
      }

      const plotlyEl = el as unknown as PlotlyElement;

      // oxlint-disable-next-line typescript/ban-types -- Plotly's event API uses generic function references
      const attached: {
        plotlyName: string;
        handler: (...args: never[]) => void;
      }[] = [];

      for (const name of EVENT_NAMES) {
        const handler = props[propName(name)];
        if (typeof handler === "function") {
          const plotlyName = plotlyEventName(name);
          plotlyEl.on(plotlyName as never, handler as never);
          attached.push({
            plotlyName,
            handler: handler as (...args: never[]) => void,
          });
        }
      }

      return () => {
        for (const { plotlyName, handler } of attached) {
          plotlyEl.removeListener(plotlyName, handler as never);
        }
      };
      // Re-sync whenever any event handler prop changes
      // oxlint-disable-next-line react-hooks/exhaustive-deps
    },
    EVENT_NAMES.map((name) => props[propName(name)]),
  );

  // Escape = clear selection. Plotly only supports double-click, so we wire up
  // the keyboard shortcut: clear per-point highlights, remove box/lasso
  // overlays, then notify the plugin to reset state.
  const { hasSelection, selectedPoints, layoutSelections, onDeselect } = props;
  useEffect(() => {
    if (!hasSelection || !onDeselect) {
      return;
    }
    const el = containerRef.current;
    if (!el) {
      return;
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) {
        return;
      }
      // Don't hijack Escape from text editors elsewhere on the page
      // (e.g. CodeMirror notebook cells, inputs, search boxes).
      const active = document.activeElement;
      if (active instanceof HTMLElement) {
        const tag = active.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          active.isContentEditable
        ) {
          return;
        }
        // With multiple plots on the page, only clear the one whose
        // container holds focus. A bare-body activeElement means nothing
        // in particular is focused, in which case it's fine to clear.
        if (active !== document.body && !el.contains(active)) {
          return;
        }
      }
      Plotly.restyle(el, "selectedpoints", null).catch(() => {});
      Plotly.relayout(el, "selections", null).catch(() => {});
      onDeselect();
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [hasSelection, onDeselect]);

  // Sync selection visuals to Plotly in one atomic `Plotly.update` pass, so
  // we don't race Plotly's own click animation.
  //
  // `selectedpoints` per trace: null = normal render, [] = all greyed,
  // [i…] = those highlighted, rest greyed. Plotly's default click handling
  // only updates the clicked trace, so we explicitly set [] on all others to
  // grey them out. `layout.selections` is cleared whenever the plugin has no
  // active overlay, otherwise the box/lasso outline sticks around.
  //
  // When the plugin is not managing selection state at all (both props
  // undefined) we leave Plotly alone — the figure may carry persistent
  // `layout.selections` or per-trace `selectedpoints` that belong to the
  // user, and wiping them would contradict the figure they passed in.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    if (!data.length) {
      return;
    }
    if (selectedPoints === undefined && layoutSelections === undefined) {
      return;
    }

    const traceIndices = data.map((_, i) => i);
    const traceUpdate: Partial<PlotlyTypes.Data> = {};
    if (selectedPoints !== undefined) {
      const byTrace = new Map<number, number[]>();
      for (const point of selectedPoints) {
        const curve =
          typeof point.curveNumber === "number" ? point.curveNumber : undefined;
        if (curve === undefined) {
          continue;
        }
        const pointIdx =
          typeof point.pointIndex === "number"
            ? point.pointIndex
            : typeof point.pointNumber === "number"
              ? point.pointNumber
              : undefined;
        if (pointIdx === undefined) {
          continue;
        }
        const indices = byTrace.get(curve) ?? [];
        indices.push(pointIdx);
        byTrace.set(curve, indices);
      }
      const anySelection = byTrace.size > 0;
      const emptyFill: number[] | null = anySelection ? [] : null;
      (traceUpdate as { selectedpoints: (number[] | null)[] }).selectedpoints =
        traceIndices.map((i) => byTrace.get(i) ?? emptyFill);
    }

    const layoutUpdate: Partial<PlotlyTypes.Layout> = {};
    if (layoutSelections !== undefined) {
      const hasActiveOverlay =
        Array.isArray(layoutSelections) && layoutSelections.length > 0;
      if (!hasActiveOverlay) {
        // `null` removes the attribute; cast because Layout's type omits it.
        (layoutUpdate as { selections: null }).selections = null;
      }
    }

    Plotly.update(el, traceUpdate, layoutUpdate, traceIndices).catch(() => {});
  }, [selectedPoints, layoutSelections, data]);

  // Window resize handler
  useEffect(() => {
    if (!useResizeHandler) {
      return;
    }

    const el = containerRef.current;
    if (!el) {
      return;
    }

    const handler = () => {
      Plotly.Plots.resize(el as unknown as PlotlyTypes.Root);
    };

    window.addEventListener("resize", handler);
    return () => {
      window.removeEventListener("resize", handler);
    };
  }, [useResizeHandler]);

  // Cleanup on unmount
  useEffect(() => {
    const el = containerRef.current;
    return () => {
      if (el) {
        Plotly.purge(el as unknown as PlotlyTypes.Root);
      }
    };
  }, []);

  return (
    <div id={divId} className={className} style={style} ref={containerRef} />
  );
};
