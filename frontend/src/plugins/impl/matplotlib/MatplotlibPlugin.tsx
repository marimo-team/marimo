/* Copyright 2026 Marimo. All rights reserved. */

import { type JSX, memo, useCallback, useEffect, useRef } from "react";
import { z } from "zod";
import type { IPlugin, IPluginProps, Setter } from "@/plugins/types";

interface Data {
  chartBase64: string;
  xBounds: [number, number];
  yBounds: [number, number];
  axesPixelBounds: [number, number, number, number]; // [left, top, right, bottom]
  width: number;
  height: number;
  selectionColor: string;
  selectionOpacity: number;
  strokeWidth: number;
  debounce: boolean;
  xScale: string;
  yScale: string;
}

interface BoxData {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
}

type T =
  | { type: "box"; has_selection: true; data: BoxData }
  | { type: "lasso"; has_selection: true; data: [number, number][] }
  | { has_selection: false }
  | undefined;

export class MatplotlibPlugin implements IPlugin<T, Data> {
  tagName = "marimo-matplotlib";

  validator = z.object({
    chartBase64: z.string(),
    xBounds: z.tuple([z.number(), z.number()]),
    yBounds: z.tuple([z.number(), z.number()]),
    axesPixelBounds: z.tuple([z.number(), z.number(), z.number(), z.number()]),
    width: z.number(),
    height: z.number(),
    selectionColor: z.string().default("#3b82f6"),
    selectionOpacity: z.number().default(0.15),
    strokeWidth: z.number().default(2),
    debounce: z.boolean(),
    xScale: z.string().default("linear"),
    yScale: z.string().default("linear"),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <MatplotlibComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface MatplotlibComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

// Pixel coordinate in canvas space
interface PixelPoint {
  x: number;
  y: number;
}

// Data coordinate in plot space
interface DataPoint {
  x: number;
  y: number;
}

type InteractionMode = "idle" | "drawing" | "dragging" | "lassoing";

interface InteractionState {
  mode: InteractionMode;
  boxStart: PixelPoint | null;
  boxEnd: PixelPoint | null;
  lassoPoints: PixelPoint[];
  dragStart: PixelPoint | null;
  rafId: number;
}

// Ray-casting point-in-polygon test
function pointInPolygon(pt: PixelPoint, polygon: PixelPoint[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;
    if (
      yi > pt.y !== yj > pt.y &&
      pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi) + xi
    ) {
      inside = !inside;
    }
  }
  return inside;
}

function isPointInBox(
  pt: PixelPoint,
  boxStart: PixelPoint,
  boxEnd: PixelPoint,
): boolean {
  const minX = Math.min(boxStart.x, boxEnd.x);
  const maxX = Math.max(boxStart.x, boxEnd.x);
  const minY = Math.min(boxStart.y, boxEnd.y);
  const maxY = Math.max(boxStart.y, boxEnd.y);
  return pt.x >= minX && pt.x <= maxX && pt.y >= minY && pt.y <= maxY;
}

const MatplotlibComponent = memo(
  ({
    chartBase64,
    xBounds,
    yBounds,
    axesPixelBounds,
    width,
    height,
    selectionColor,
    selectionOpacity,
    strokeWidth,
    debounce,
    xScale,
    yScale,
    value,
    setValue,
  }: MatplotlibComponentProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const loadedImageRef = useRef<HTMLImageElement | null>(null);

    const [axLeft, axTop, axRight, axBottom] = axesPixelBounds;
    const axWidth = axRight - axLeft;
    const axHeight = axBottom - axTop;

    // All interaction state lives in a ref to avoid React re-renders during drawing
    const interactionRef = useRef<InteractionState>({
      mode: "idle",
      boxStart: null,
      boxEnd: null,
      lassoPoints: [],
      dragStart: null,
      rafId: 0,
    });

    // Keep stable references to props that event handlers need
    const propsRef = useRef({
      axLeft,
      axTop,
      axRight,
      axBottom,
      axWidth,
      axHeight,
      xBounds,
      yBounds,
      xScale,
      yScale,
      selectionColor,
      selectionOpacity,
      strokeWidth,
      debounce,
      setValue,
    });
    propsRef.current = {
      axLeft,
      axTop,
      axRight,
      axBottom,
      axWidth,
      axHeight,
      xBounds,
      yBounds,
      xScale,
      yScale,
      selectionColor,
      selectionOpacity,
      strokeWidth,
      debounce,
      setValue,
    };

    // Convert pixel coords (relative to canvas) to data coords
    const pixelToData = useCallback((px: PixelPoint): DataPoint => {
      const p = propsRef.current;
      const fracX = (px.x - p.axLeft) / p.axWidth;
      const fracY = (px.y - p.axTop) / p.axHeight;

      let dataX: number;
      if (p.xScale === "log") {
        const logMin = Math.log10(p.xBounds[0]);
        const logMax = Math.log10(p.xBounds[1]);
        dataX = 10 ** (logMin + fracX * (logMax - logMin));
      } else {
        dataX = p.xBounds[0] + fracX * (p.xBounds[1] - p.xBounds[0]);
      }

      let dataY: number;
      if (p.yScale === "log") {
        const logMin = Math.log10(p.yBounds[0]);
        const logMax = Math.log10(p.yBounds[1]);
        dataY = 10 ** (logMax - fracY * (logMax - logMin));
      } else {
        dataY = p.yBounds[1] - fracY * (p.yBounds[1] - p.yBounds[0]);
      }

      return { x: dataX, y: dataY };
    }, []);

    // Convert data coords to pixel coords
    const dataToPixel = useCallback((data: DataPoint): PixelPoint => {
      const p = propsRef.current;
      let fracX: number;
      if (p.xScale === "log") {
        fracX =
          (Math.log10(data.x) - Math.log10(p.xBounds[0])) /
          (Math.log10(p.xBounds[1]) - Math.log10(p.xBounds[0]));
      } else {
        fracX = (data.x - p.xBounds[0]) / (p.xBounds[1] - p.xBounds[0]);
      }

      let fracY: number;
      if (p.yScale === "log") {
        fracY =
          (Math.log10(p.yBounds[1]) - Math.log10(data.y)) /
          (Math.log10(p.yBounds[1]) - Math.log10(p.yBounds[0]));
      } else {
        fracY = (p.yBounds[1] - data.y) / (p.yBounds[1] - p.yBounds[0]);
      }

      return {
        x: p.axLeft + fracX * p.axWidth,
        y: p.axTop + fracY * p.axHeight,
      };
    }, []);

    // Draw the canvas (base image + selection overlays)
    const drawCanvas = useCallback(() => {
      const canvas = canvasRef.current;
      const img = loadedImageRef.current;
      if (!canvas || !img) {
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return;
      }

      const p = propsRef.current;
      const state = interactionRef.current;

      // Clear and draw the base image
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // Draw box selection overlay
      if (state.boxStart && state.boxEnd) {
        const x = Math.min(state.boxStart.x, state.boxEnd.x);
        const y = Math.min(state.boxStart.y, state.boxEnd.y);
        const w = Math.abs(state.boxEnd.x - state.boxStart.x);
        const h = Math.abs(state.boxEnd.y - state.boxStart.y);

        ctx.save();
        ctx.fillStyle = p.selectionColor;
        ctx.globalAlpha = p.selectionOpacity;
        ctx.fillRect(x, y, w, h);
        ctx.restore();

        ctx.strokeStyle = p.selectionColor;
        ctx.lineWidth = p.strokeWidth;
        ctx.strokeRect(x, y, w, h);
      }

      // Draw lasso selection overlay
      if (state.lassoPoints.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(state.lassoPoints[0].x, state.lassoPoints[0].y);
        for (let i = 1; i < state.lassoPoints.length; i++) {
          ctx.lineTo(state.lassoPoints[i].x, state.lassoPoints[i].y);
        }
        ctx.closePath();

        ctx.save();
        ctx.fillStyle = p.selectionColor;
        ctx.globalAlpha = p.selectionOpacity;
        ctx.fill();
        ctx.restore();

        ctx.strokeStyle = p.selectionColor;
        ctx.lineWidth = p.strokeWidth;
        ctx.stroke();
      }
    }, []);

    function scheduleRedraw() {
      cancelAnimationFrame(interactionRef.current.rafId);
      interactionRef.current.rafId = requestAnimationFrame(drawCanvas);
    }

    // Redraw when selection style props change
    useEffect(() => {
      drawCanvas();
    }, [selectionColor, selectionOpacity, strokeWidth, drawCanvas]);

    // Load image — clear selection and redraw when the chart changes
    useEffect(() => {
      let cancelled = false;
      interactionRef.current.boxStart = null;
      interactionRef.current.boxEnd = null;
      interactionRef.current.lassoPoints = [];
      interactionRef.current.mode = "idle";
      const img = new Image();
      img.onload = () => {
        if (cancelled) {
          return;
        }
        loadedImageRef.current = img;
        drawCanvas();
      };
      img.src = chartBase64;
      return () => {
        cancelled = true;
      };
    }, [chartBase64, drawCanvas]);

    // Clamp a pixel point to the axes area
    function clampToAxes(pt: PixelPoint): PixelPoint {
      const p = propsRef.current;
      return {
        x: Math.max(p.axLeft, Math.min(p.axRight, pt.x)),
        y: Math.max(p.axTop, Math.min(p.axBottom, pt.y)),
      };
    }

    // Emit box selection to the backend
    function emitBoxSelection(
      bStart: PixelPoint | null,
      bEnd: PixelPoint | null,
    ) {
      if (bStart && bEnd) {
        const d1 = pixelToData(bStart);
        const d2 = pixelToData(bEnd);
        propsRef.current.setValue({
          type: "box",
          has_selection: true,
          data: {
            x_min: Math.min(d1.x, d2.x),
            x_max: Math.max(d1.x, d2.x),
            y_min: Math.min(d1.y, d2.y),
            y_max: Math.max(d1.y, d2.y),
          },
        });
      }
    }

    // Emit lasso selection to the backend
    function emitLassoSelection(points: PixelPoint[]) {
      if (points.length >= 3) {
        const data: [number, number][] = points.map((p) => {
          const d = pixelToData(p);
          return [d.x, d.y];
        });
        propsRef.current.setValue({
          type: "lasso",
          has_selection: true,
          data,
        });
      }
    }

    // Clear selection
    function clearSelection() {
      interactionRef.current.boxStart = null;
      interactionRef.current.boxEnd = null;
      interactionRef.current.lassoPoints = [];
      interactionRef.current.mode = "idle";
      propsRef.current.setValue({ has_selection: false });
      scheduleRedraw();
    }

    // Check if a pixel point is inside the current selection
    function isPointInSelection(pt: PixelPoint): boolean {
      const state = interactionRef.current;
      if (state.boxStart && state.boxEnd) {
        return isPointInBox(pt, state.boxStart, state.boxEnd);
      }
      if (state.lassoPoints.length >= 3) {
        return pointInPolygon(pt, state.lassoPoints);
      }
      return false;
    }

    function hasSelection(): boolean {
      const state = interactionRef.current;
      return (
        (state.boxStart !== null && state.boxEnd !== null) ||
        state.lassoPoints.length >= 3
      );
    }

    // Get canvas-relative coordinates from a pointer event
    function getCanvasPoint(e: React.PointerEvent): PixelPoint {
      const canvas = canvasRef.current;
      if (!canvas) {
        return { x: 0, y: 0 };
      }
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;

      return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
      };
    }

    // Update cursor style based on mouse position
    function updateCursor(pt: PixelPoint) {
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }
      const p = propsRef.current;
      const inAxes =
        pt.x >= p.axLeft &&
        pt.x <= p.axRight &&
        pt.y >= p.axTop &&
        pt.y <= p.axBottom;

      if (!inAxes) {
        canvas.style.cursor = "default";
      } else if (hasSelection() && isPointInSelection(pt)) {
        canvas.style.cursor = "move";
      } else {
        canvas.style.cursor = "crosshair";
      }
    }

    const handlePointerDown = useCallback(
      (e: React.PointerEvent) => {
        const canvas = canvasRef.current;
        if (canvas) {
          canvas.setPointerCapture(e.pointerId);
        }
        containerRef.current?.focus();
        const pt = getCanvasPoint(e);
        const state = interactionRef.current;

        // Shift+click → start lasso
        if (e.shiftKey) {
          state.boxStart = null;
          state.boxEnd = null;
          state.mode = "lassoing";
          state.lassoPoints = [clampToAxes(pt)];
          scheduleRedraw();
          return;
        }

        // If clicking inside existing selection, start dragging
        if (hasSelection() && isPointInSelection(pt)) {
          state.mode = "dragging";
          state.dragStart = pt;
          return;
        }

        // If clicking outside selection with an existing one, clear it
        // then fall through to start a new box selection
        if (hasSelection() && !isPointInSelection(pt)) {
          clearSelection();
        }

        // Start new box selection
        const clamped = clampToAxes(pt);
        state.mode = "drawing";
        state.boxStart = clamped;
        state.boxEnd = clamped;
        scheduleRedraw();
      },
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [],
    );

    const handlePointerMove = useCallback(
      (e: React.PointerEvent) => {
        const pt = getCanvasPoint(e);
        const state = interactionRef.current;
        const p = propsRef.current;

        // Update cursor when idle
        if (state.mode === "idle") {
          updateCursor(pt);
        }

        // Lassoing: append clamped point
        if (state.mode === "lassoing") {
          state.lassoPoints.push(clampToAxes(pt));
          scheduleRedraw();
          return;
        }

        if (state.mode === "dragging" && state.dragStart) {
          let dx = pt.x - state.dragStart.x;
          let dy = pt.y - state.dragStart.y;
          state.dragStart = pt;

          if (state.boxStart && state.boxEnd) {
            // Clamp delta so the entire box stays in bounds
            const minX = Math.min(state.boxStart.x, state.boxEnd.x);
            const maxX = Math.max(state.boxStart.x, state.boxEnd.x);
            const minY = Math.min(state.boxStart.y, state.boxEnd.y);
            const maxY = Math.max(state.boxStart.y, state.boxEnd.y);
            dx = Math.max(p.axLeft - minX, Math.min(p.axRight - maxX, dx));
            dy = Math.max(p.axTop - minY, Math.min(p.axBottom - maxY, dy));
            state.boxStart = {
              x: state.boxStart.x + dx,
              y: state.boxStart.y + dy,
            };
            state.boxEnd = {
              x: state.boxEnd.x + dx,
              y: state.boxEnd.y + dy,
            };
            scheduleRedraw();
            if (!p.debounce) {
              emitBoxSelection(state.boxStart, state.boxEnd);
            }
          } else if (state.lassoPoints.length >= 3) {
            // Clamp delta so the entire lasso stays in bounds
            let lMinX = Number.POSITIVE_INFINITY;
            let lMaxX = Number.NEGATIVE_INFINITY;
            let lMinY = Number.POSITIVE_INFINITY;
            let lMaxY = Number.NEGATIVE_INFINITY;
            for (const lp of state.lassoPoints) {
              if (lp.x < lMinX) {
                lMinX = lp.x;
              }
              if (lp.x > lMaxX) {
                lMaxX = lp.x;
              }
              if (lp.y < lMinY) {
                lMinY = lp.y;
              }
              if (lp.y > lMaxY) {
                lMaxY = lp.y;
              }
            }
            dx = Math.max(p.axLeft - lMinX, Math.min(p.axRight - lMaxX, dx));
            dy = Math.max(p.axTop - lMinY, Math.min(p.axBottom - lMaxY, dy));
            for (let i = 0; i < state.lassoPoints.length; i++) {
              state.lassoPoints[i] = {
                x: state.lassoPoints[i].x + dx,
                y: state.lassoPoints[i].y + dy,
              };
            }
            scheduleRedraw();
            if (!p.debounce) {
              emitLassoSelection(state.lassoPoints);
            }
          }
          return;
        }

        if (state.mode === "drawing") {
          const clamped = clampToAxes(pt);
          state.boxEnd = clamped;
          scheduleRedraw();
          if (!p.debounce) {
            emitBoxSelection(state.boxStart, clamped);
          }
        }
      },
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [],
    );

    const handlePointerUp = useCallback((e: React.PointerEvent) => {
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.releasePointerCapture(e.pointerId);
      }

      const state = interactionRef.current;
      const p = propsRef.current;

      if (state.mode === "lassoing") {
        state.mode = "idle";
        if (state.lassoPoints.length >= 3) {
          emitLassoSelection(state.lassoPoints);
        } else {
          // Degenerate lasso, clear
          state.lassoPoints = [];
          propsRef.current.setValue({ has_selection: false });
        }
        scheduleRedraw();
        return;
      }

      if (state.mode === "dragging") {
        state.mode = "idle";
        state.dragStart = null;
        if (p.debounce) {
          if (state.boxStart && state.boxEnd) {
            emitBoxSelection(state.boxStart, state.boxEnd);
          } else if (state.lassoPoints.length >= 3) {
            emitLassoSelection(state.lassoPoints);
          }
        }
        return;
      }

      if (state.mode === "drawing") {
        state.mode = "idle";
        if (p.debounce) {
          emitBoxSelection(state.boxStart, state.boxEnd);
        }
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Escape key cancels in-progress selection (scoped to container)
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        const state = interactionRef.current;
        if (state.mode === "drawing" || state.mode === "lassoing") {
          state.mode = "idle";
          state.boxStart = null;
          state.boxEnd = null;
          state.lassoPoints = [];
          scheduleRedraw();
        } else if (hasSelection()) {
          clearSelection();
        }
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Restore selection from value (e.g., when re-rendered by backend)
    useEffect(() => {
      if (!value || !("has_selection" in value) || !value.has_selection) {
        return;
      }

      if (value.type === "box") {
        const sel = value.data;
        const start = dataToPixel({ x: sel.x_min, y: sel.y_min });
        const end = dataToPixel({ x: sel.x_max, y: sel.y_max });
        interactionRef.current.boxStart = start;
        interactionRef.current.boxEnd = end;
        interactionRef.current.lassoPoints = [];
      } else if (value.type === "lasso") {
        const points = value.data.map(([vx, vy]) =>
          dataToPixel({ x: vx, y: vy }),
        );
        interactionRef.current.lassoPoints = points;
        interactionRef.current.boxStart = null;
        interactionRef.current.boxEnd = null;
      }
      scheduleRedraw();
      // Only restore on mount
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Clean up rAF on unmount
    useEffect(() => {
      return () => cancelAnimationFrame(interactionRef.current.rafId);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
      <div
        ref={containerRef}
        className="relative inline-block select-none outline-none"
        role="application"
        tabIndex={-1}
        onKeyDown={handleKeyDown}
      >
        <canvas
          ref={canvasRef}
          className="block cursor-crosshair"
          width={width}
          height={height}
          style={{
            width: `${width}px`,
            height: `${height}px`,
            maxWidth: "100%",
            touchAction: "none",
          }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        />
      </div>
    );
  },
);
MatplotlibComponent.displayName = "MatplotlibComponent";
