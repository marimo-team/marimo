/* Copyright 2026 Marimo. All rights reserved. */

import type * as PlotlyTypes from "plotly.js";
// Import the pre-built dist bundle, not the source entry point.
// The source entry point requires Node.js polyfills (e.g. `buffer/`)
// that are unavailable in the browser/bundler environment.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
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

export interface PlotProps {
  data: PlotlyTypes.Data[];
  layout: Partial<PlotlyTypes.Layout>;
  frames?: PlotlyTypes.Frame[];
  config?: Partial<PlotlyTypes.Config>;
  className?: string;
  style?: React.CSSProperties;
  useResizeHandler?: boolean;
  divId?: string;
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

      // eslint-disable-next-line @typescript-eslint/ban-types -- Plotly's event API uses generic function references
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
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    EVENT_NAMES.map((name) => props[propName(name)]),
  );

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
