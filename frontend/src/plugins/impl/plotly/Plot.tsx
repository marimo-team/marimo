/* Copyright 2026 Marimo. All rights reserved. */

import * as Plotly from "plotly.js";
import { useEffect, useRef } from "react";

// Plotly attaches `on` and `removeListener` to the DOM element at runtime.
// The @types/plotly.js PlotlyHTMLElement type includes `on` and `removeAllListeners`
// but not the per-handler `removeListener`. We extend the type to include it.
interface PlotlyElement extends Plotly.PlotlyHTMLElement {
  removeListener(event: string, handler: (...args: never[]) => void): void;
}

export interface Figure {
  data: Plotly.Data[];
  layout: Partial<Plotly.Layout>;
  frames: Plotly.Frame[] | null;
}

export interface PlotProps {
  data: Plotly.Data[];
  layout: Partial<Plotly.Layout>;
  frames?: Plotly.Frame[];
  config?: Partial<Plotly.Config>;
  className?: string;
  style?: React.CSSProperties;
  useResizeHandler?: boolean;
  divId?: string;
  onRelayout?: (event: Plotly.PlotRelayoutEvent) => void;
  onRelayouting?: (event: Plotly.PlotRelayoutEvent) => void;
  onSelected?: (event: Plotly.PlotSelectionEvent) => void;
  onDeselect?: () => void;
  onSunburstClick?: (event: Plotly.PlotMouseEvent) => void;
  onTreemapClick?: (event: Plotly.PlotMouseEvent) => void;
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
          return Plotly.addFrames(el as unknown as Plotly.Root, frames);
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
      Plotly.Plots.resize(el as unknown as Plotly.Root);
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
        Plotly.purge(el as unknown as Plotly.Root);
      }
    };
  }, []);

  return (
    <div id={divId} className={className} style={style} ref={containerRef} />
  );
};
