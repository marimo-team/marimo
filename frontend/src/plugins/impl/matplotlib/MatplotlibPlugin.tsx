/* Copyright 2026 Marimo. All rights reserved. */

import {
  type JSX,
  memo,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { z } from "zod";
import type { IPlugin, IPluginProps, Setter } from "@/plugins/types";

import "./matplotlib.css";

interface Data {
  chartBase64: string;
  xBounds: [number, number];
  yBounds: [number, number];
  axesPixelBounds: [number, number, number, number]; // [left, top, right, bottom]
  width: number;
  height: number;
  modes: string[];
  selectionColor: string;
  selectionOpacity: number;
  strokeWidth: number;
}

interface BoxSelection {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
}

interface LassoSelection {
  vertices: [number, number][];
}

type T =
  | {
      mode: string;
      has_selection: boolean;
      selection: BoxSelection | LassoSelection;
    }
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
    modes: z.array(z.string()),
    selectionColor: z.string(),
    selectionOpacity: z.number(),
    strokeWidth: z.number(),
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

const MatplotlibComponent = memo(
  ({
    chartBase64,
    xBounds,
    yBounds,
    axesPixelBounds,
    width,
    height,
    modes,
    selectionColor,
    selectionOpacity,
    strokeWidth,
    value,
    setValue,
  }: MatplotlibComponentProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imageRef = useRef<HTMLImageElement | null>(null);
    const [mode, setMode] = useState<string>(modes[0] || "box");
    const [imageLoaded, setImageLoaded] = useState(false);

    // Selection state in pixel coordinates
    const [isDrawing, setIsDrawing] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const dragStartRef = useRef<PixelPoint | null>(null);
    const selectionStartRef = useRef<PixelPoint | null>(null);

    // Box selection: start and end in pixels
    const [boxStart, setBoxStart] = useState<PixelPoint | null>(null);
    const [boxEnd, setBoxEnd] = useState<PixelPoint | null>(null);

    // Lasso selection: points in pixels
    const [lassoPoints, setLassoPoints] = useState<PixelPoint[]>([]);

    // For dragging: stored offsets from the selection
    const dragOffsetRef = useRef<PixelPoint>({ x: 0, y: 0 });

    const [axLeft, axTop, axRight, axBottom] = axesPixelBounds;
    const axWidth = axRight - axLeft;
    const axHeight = axBottom - axTop;

    // Convert pixel coords (relative to canvas) to data coords
    const pixelToData = useCallback(
      (px: PixelPoint): PixelPoint => {
        const fracX = (px.x - axLeft) / axWidth;
        const fracY = (px.y - axTop) / axHeight;
        return {
          x: xBounds[0] + fracX * (xBounds[1] - xBounds[0]),
          // Y-axis is inverted in pixel space (top=0 in pixels, but top=yMax in data)
          y: yBounds[1] - fracY * (yBounds[1] - yBounds[0]),
        };
      },
      [axLeft, axTop, axWidth, axHeight, xBounds, yBounds],
    );

    // Convert data coords to pixel coords
    const dataToPixel = useCallback(
      (data: PixelPoint): PixelPoint => {
        const fracX = (data.x - xBounds[0]) / (xBounds[1] - xBounds[0]);
        const fracY = (yBounds[1] - data.y) / (yBounds[1] - yBounds[0]);
        return {
          x: axLeft + fracX * axWidth,
          y: axTop + fracY * axHeight,
        };
      },
      [axLeft, axTop, axWidth, axHeight, xBounds, yBounds],
    );

    // Load image
    useEffect(() => {
      const img = new Image();
      img.onload = () => {
        imageRef.current = img;
        setImageLoaded(true);
      };
      img.src = chartBase64;
    }, [chartBase64]);

    // Clamp a pixel point to the axes area
    const clampToAxes = useCallback(
      (pt: PixelPoint): PixelPoint => ({
        x: Math.max(axLeft, Math.min(axRight, pt.x)),
        y: Math.max(axTop, Math.min(axBottom, pt.y)),
      }),
      [axLeft, axTop, axRight, axBottom],
    );

    // Emit the current selection as a value
    const emitSelection = useCallback(
      (
        currentMode: string,
        bStart: PixelPoint | null,
        bEnd: PixelPoint | null,
        lPoints: PixelPoint[],
      ) => {
        if (currentMode === "box" && bStart && bEnd) {
          const d1 = pixelToData(bStart);
          const d2 = pixelToData(bEnd);
          setValue({
            mode: "box",
            has_selection: true,
            selection: {
              x_min: Math.min(d1.x, d2.x),
              x_max: Math.max(d1.x, d2.x),
              y_min: Math.min(d1.y, d2.y),
              y_max: Math.max(d1.y, d2.y),
            },
          });
        } else if (currentMode === "lasso" && lPoints.length >= 3) {
          const vertices = lPoints.map((p) => {
            const d = pixelToData(p);
            return [d.x, d.y] as [number, number];
          });
          setValue({
            mode: "lasso",
            has_selection: true,
            selection: { vertices },
          });
        }
      },
      [pixelToData, setValue],
    );

    // Clear selection
    const clearSelection = useCallback(() => {
      setBoxStart(null);
      setBoxEnd(null);
      setLassoPoints([]);
      setValue(undefined);
    }, [setValue]);

    // Check if a pixel point is inside the current selection
    const isPointInSelection = useCallback(
      (pt: PixelPoint): boolean => {
        if (mode === "box" && boxStart && boxEnd) {
          const minX = Math.min(boxStart.x, boxEnd.x);
          const maxX = Math.max(boxStart.x, boxEnd.x);
          const minY = Math.min(boxStart.y, boxEnd.y);
          const maxY = Math.max(boxStart.y, boxEnd.y);
          return pt.x >= minX && pt.x <= maxX && pt.y >= minY && pt.y <= maxY;
        }
        if (mode === "lasso" && lassoPoints.length >= 3) {
          return pointInPolygon(pt, lassoPoints);
        }
        return false;
      },
      [mode, boxStart, boxEnd, lassoPoints],
    );

    // Get canvas-relative coordinates from a mouse/touch event
    const getCanvasPoint = useCallback(
      (e: React.MouseEvent | React.TouchEvent): PixelPoint => {
        const canvas = canvasRef.current;
        if (!canvas) {
          return { x: 0, y: 0 };
        }
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        let clientX: number;
        let clientY: number;
        if ("touches" in e) {
          const touch =
            e.touches[0] || (e as React.TouchEvent).changedTouches[0];
          clientX = touch.clientX;
          clientY = touch.clientY;
        } else {
          clientX = e.clientX;
          clientY = e.clientY;
        }

        return {
          x: (clientX - rect.left) * scaleX,
          y: (clientY - rect.top) * scaleY,
        };
      },
      [],
    );

    // Has existing selection?
    const hasSelection =
      (mode === "box" && boxStart !== null && boxEnd !== null) ||
      (mode === "lasso" && lassoPoints.length >= 3);

    // Mouse/touch handlers
    const handlePointerDown = useCallback(
      (e: React.MouseEvent | React.TouchEvent) => {
        const pt = getCanvasPoint(e);

        // If clicking inside existing selection, start dragging
        if (hasSelection && isPointInSelection(pt)) {
          setIsDragging(true);
          dragStartRef.current = pt;
          // Store offset from selection position for smooth dragging
          if (mode === "box" && boxStart) {
            dragOffsetRef.current = {
              x: pt.x - boxStart.x,
              y: pt.y - boxStart.y,
            };
          } else if (mode === "lasso" && lassoPoints.length > 0) {
            // Use centroid offset
            const cx =
              lassoPoints.reduce((s, p) => s + p.x, 0) / lassoPoints.length;
            const cy =
              lassoPoints.reduce((s, p) => s + p.y, 0) / lassoPoints.length;
            dragOffsetRef.current = { x: pt.x - cx, y: pt.y - cy };
          }
          return;
        }

        // If clicking outside selection with an existing one, clear it
        if (hasSelection && !isPointInSelection(pt)) {
          clearSelection();
          return;
        }

        // Start new selection
        const clamped = clampToAxes(pt);
        setIsDrawing(true);
        selectionStartRef.current = clamped;

        if (mode === "box") {
          setBoxStart(clamped);
          setBoxEnd(clamped);
        } else if (mode === "lasso") {
          setLassoPoints([clamped]);
        }
      },
      [
        getCanvasPoint,
        hasSelection,
        isPointInSelection,
        mode,
        boxStart,
        lassoPoints,
        clearSelection,
        clampToAxes,
      ],
    );

    const handlePointerMove = useCallback(
      (e: React.MouseEvent | React.TouchEvent) => {
        const pt = getCanvasPoint(e);

        if (isDragging && dragStartRef.current) {
          let dx = pt.x - dragStartRef.current.x;
          let dy = pt.y - dragStartRef.current.y;
          dragStartRef.current = pt;

          if (mode === "box" && boxStart && boxEnd) {
            // Clamp delta so the entire box stays in bounds
            const minX = Math.min(boxStart.x, boxEnd.x);
            const maxX = Math.max(boxStart.x, boxEnd.x);
            const minY = Math.min(boxStart.y, boxEnd.y);
            const maxY = Math.max(boxStart.y, boxEnd.y);
            dx = Math.max(axLeft - minX, Math.min(axRight - maxX, dx));
            dy = Math.max(axTop - minY, Math.min(axBottom - maxY, dy));
            setBoxStart({ x: boxStart.x + dx, y: boxStart.y + dy });
            setBoxEnd({ x: boxEnd.x + dx, y: boxEnd.y + dy });
          } else if (mode === "lasso") {
            setLassoPoints((prev) => {
              // Clamp delta so no vertex leaves bounds
              let clampedDx = dx;
              let clampedDy = dy;
              for (const p of prev) {
                clampedDx = Math.max(
                  axLeft - p.x,
                  Math.min(axRight - p.x, clampedDx),
                );
                clampedDy = Math.max(
                  axTop - p.y,
                  Math.min(axBottom - p.y, clampedDy),
                );
              }
              return prev.map((p) => ({
                x: p.x + clampedDx,
                y: p.y + clampedDy,
              }));
            });
          }
          return;
        }

        if (isDrawing) {
          const clamped = clampToAxes(pt);
          if (mode === "box") {
            setBoxEnd(clamped);
          } else if (mode === "lasso") {
            setLassoPoints((prev) => [...prev, clamped]);
          }
        }
      },
      [
        getCanvasPoint,
        isDragging,
        isDrawing,
        mode,
        boxStart,
        boxEnd,
        clampToAxes,
        axLeft,
        axTop,
        axRight,
        axBottom,
      ],
    );

    const handlePointerUp = useCallback(() => {
      if (isDragging) {
        setIsDragging(false);
        dragStartRef.current = null;
        // Re-emit with updated positions
        emitSelection(mode, boxStart, boxEnd, lassoPoints);
        return;
      }

      if (isDrawing) {
        setIsDrawing(false);
        selectionStartRef.current = null;
        emitSelection(mode, boxStart, boxEnd, lassoPoints);
      }
    }, [
      isDragging,
      isDrawing,
      mode,
      boxStart,
      boxEnd,
      lassoPoints,
      emitSelection,
    ]);

    // Draw on canvas
    useEffect(() => {
      const canvas = canvasRef.current;
      const img = imageRef.current;
      if (!canvas || !img || !imageLoaded) {
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return;
      }

      // Clear and draw the base image
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // Draw selection overlay
      if (mode === "box" && boxStart && boxEnd) {
        const x = Math.min(boxStart.x, boxEnd.x);
        const y = Math.min(boxStart.y, boxEnd.y);
        const w = Math.abs(boxEnd.x - boxStart.x);
        const h = Math.abs(boxEnd.y - boxStart.y);

        ctx.fillStyle = selectionColor;
        ctx.globalAlpha = selectionOpacity;
        ctx.fillRect(x, y, w, h);

        ctx.globalAlpha = 1;
        ctx.strokeStyle = selectionColor;
        ctx.lineWidth = strokeWidth;
        ctx.strokeRect(x, y, w, h);
      } else if (mode === "lasso" && lassoPoints.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(lassoPoints[0].x, lassoPoints[0].y);
        for (let i = 1; i < lassoPoints.length; i++) {
          ctx.lineTo(lassoPoints[i].x, lassoPoints[i].y);
        }
        ctx.closePath();

        ctx.fillStyle = selectionColor;
        ctx.globalAlpha = selectionOpacity;
        ctx.fill();

        ctx.globalAlpha = 1;
        ctx.strokeStyle = selectionColor;
        ctx.lineWidth = strokeWidth;
        ctx.stroke();
      }
    }, [
      imageLoaded,
      mode,
      boxStart,
      boxEnd,
      lassoPoints,
      selectionColor,
      selectionOpacity,
      strokeWidth,
    ]);

    // When mode changes, clear selection
    const handleModeChange = useCallback(
      (newMode: string) => {
        if (newMode !== mode) {
          clearSelection();
          setMode(newMode);
        }
      },
      [mode, clearSelection],
    );

    // Restore selection from value (e.g., when re-rendered by backend)
    useEffect(() => {
      if (!value || !value.has_selection) {
        return;
      }

      if (value.mode === "box" && "x_min" in value.selection) {
        const sel = value.selection as BoxSelection;
        const start = dataToPixel({ x: sel.x_min, y: sel.y_min });
        const end = dataToPixel({ x: sel.x_max, y: sel.y_max });
        setBoxStart(start);
        setBoxEnd(end);
        setMode("box");
      } else if (value.mode === "lasso" && "vertices" in value.selection) {
        const sel = value.selection as LassoSelection;
        const pts = sel.vertices.map((v) => dataToPixel({ x: v[0], y: v[1] }));
        setLassoPoints(pts);
        setMode("lasso");
      }
      // Only restore on mount / when value identity changes from backend
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
      <div className="matplotlib-container">
        {modes.length > 1 && (
          <div className="matplotlib-controls">
            {modes.map((m) => (
              <button
                key={m}
                type="button"
                className={`matplotlib-mode-btn ${m === mode ? "active" : ""}`}
                onClick={() => handleModeChange(m)}
              >
                {m === "box" ? "Box" : "Lasso"}
              </button>
            ))}
            {hasSelection && (
              <button
                type="button"
                className="matplotlib-clear-btn"
                onClick={clearSelection}
              >
                Clear
              </button>
            )}
          </div>
        )}
        <canvas
          ref={canvasRef}
          className="matplotlib-canvas"
          width={width}
          height={height}
          style={{
            width: `${width}px`,
            height: `${height}px`,
            maxWidth: "100%",
          }}
          onMouseDown={handlePointerDown}
          onMouseMove={handlePointerMove}
          onMouseUp={handlePointerUp}
          onMouseLeave={handlePointerUp}
          onTouchStart={handlePointerDown}
          onTouchMove={handlePointerMove}
          onTouchEnd={handlePointerUp}
        />
      </div>
    );
  },
);
MatplotlibComponent.displayName = "MatplotlibComponent";

/**
 * Point-in-polygon test using ray casting algorithm.
 */
function pointInPolygon(pt: PixelPoint, polygon: PixelPoint[]): boolean {
  let inside = false;
  const n = polygon.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
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
