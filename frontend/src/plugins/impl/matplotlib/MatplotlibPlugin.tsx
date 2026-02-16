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
  selectionColor: string;
  selectionOpacity: number;
  strokeWidth: number;
  debounce: boolean;
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
    value,
    setValue,
  }: MatplotlibComponentProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [loadedImage, setLoadedImage] = useState<HTMLImageElement | null>(
      null,
    );

    // Box selection state in pixel coordinates
    const [isDrawing, setIsDrawing] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const dragStartRef = useRef<PixelPoint | null>(null);

    // Box selection: start and end in pixels
    const [boxStart, setBoxStart] = useState<PixelPoint | null>(null);
    const [boxEnd, setBoxEnd] = useState<PixelPoint | null>(null);

    // Lasso selection state
    const [isLassoing, setIsLassoing] = useState(false);
    const [lassoPoints, setLassoPoints] = useState<PixelPoint[]>([]);

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

    // Load image — clear selection and redraw when the chart changes
    useEffect(() => {
      setBoxStart(null);
      setBoxEnd(null);
      setLassoPoints([]);
      const img = new Image();
      img.onload = () => setLoadedImage(img);
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

    // Emit box selection
    const emitBoxSelection = useCallback(
      (bStart: PixelPoint | null, bEnd: PixelPoint | null) => {
        if (bStart && bEnd) {
          const d1 = pixelToData(bStart);
          const d2 = pixelToData(bEnd);
          setValue({
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
      },
      [pixelToData, setValue],
    );

    // Emit lasso selection
    const emitLassoSelection = useCallback(
      (points: PixelPoint[]) => {
        if (points.length >= 3) {
          const data: [number, number][] = points.map((p) => {
            const d = pixelToData(p);
            return [d.x, d.y];
          });
          setValue({
            type: "lasso",
            has_selection: true,
            data,
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
      setValue({ has_selection: false });
    }, [setValue]);

    // What kind of selection is currently active?
    const hasBoxSelection = boxStart !== null && boxEnd !== null;
    const hasLassoSelection = lassoPoints.length >= 3;
    const hasSelection = hasBoxSelection || hasLassoSelection;

    // Check if a pixel point is inside the current selection (box or lasso)
    const isPointInSelection = useCallback(
      (pt: PixelPoint): boolean => {
        if (hasBoxSelection) {
          const minX = Math.min(boxStart.x, boxEnd.x);
          const maxX = Math.max(boxStart.x, boxEnd.x);
          const minY = Math.min(boxStart.y, boxEnd.y);
          const maxY = Math.max(boxStart.y, boxEnd.y);
          return pt.x >= minX && pt.x <= maxX && pt.y >= minY && pt.y <= maxY;
        }
        if (hasLassoSelection) {
          return pointInPolygon(pt, lassoPoints);
        }
        return false;
      },
      [hasBoxSelection, hasLassoSelection, boxStart, boxEnd, lassoPoints],
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

    // Check if Shift key is held
    const isShiftHeld = useCallback(
      (e: React.MouseEvent | React.TouchEvent): boolean => {
        if ("shiftKey" in e) {
          return e.shiftKey;
        }
        return false;
      },
      [],
    );

    // Mouse/touch handlers
    const handlePointerDown = useCallback(
      (e: React.MouseEvent | React.TouchEvent) => {
        const pt = getCanvasPoint(e);

        // Shift+click → start lasso
        if (isShiftHeld(e)) {
          // Clear any existing box selection
          setBoxStart(null);
          setBoxEnd(null);
          setIsDrawing(false);
          setIsDragging(false);

          const clamped = clampToAxes(pt);
          setIsLassoing(true);
          setLassoPoints([clamped]);
          return;
        }

        // If clicking inside existing selection, start dragging
        if (hasSelection && isPointInSelection(pt)) {
          setIsDragging(true);
          dragStartRef.current = pt;
          return;
        }

        // If clicking outside selection with an existing one, clear it
        if (hasSelection && !isPointInSelection(pt)) {
          clearSelection();
          return;
        }

        // Start new box selection
        const clamped = clampToAxes(pt);
        setIsDrawing(true);
        setBoxStart(clamped);
        setBoxEnd(clamped);
      },
      [
        getCanvasPoint,
        isShiftHeld,
        hasSelection,
        isPointInSelection,
        clearSelection,
        clampToAxes,
      ],
    );

    const handlePointerMove = useCallback(
      (e: React.MouseEvent | React.TouchEvent) => {
        const pt = getCanvasPoint(e);

        // Lassoing: append clamped point
        if (isLassoing) {
          const clamped = clampToAxes(pt);
          setLassoPoints((prev) => [...prev, clamped]);
          return;
        }

        if (isDragging && dragStartRef.current) {
          let dx = pt.x - dragStartRef.current.x;
          let dy = pt.y - dragStartRef.current.y;
          dragStartRef.current = pt;

          if (hasBoxSelection && boxStart && boxEnd) {
            // Clamp delta so the entire box stays in bounds
            const minX = Math.min(boxStart.x, boxEnd.x);
            const maxX = Math.max(boxStart.x, boxEnd.x);
            const minY = Math.min(boxStart.y, boxEnd.y);
            const maxY = Math.max(boxStart.y, boxEnd.y);
            dx = Math.max(axLeft - minX, Math.min(axRight - maxX, dx));
            dy = Math.max(axTop - minY, Math.min(axBottom - maxY, dy));
            const newStart = { x: boxStart.x + dx, y: boxStart.y + dy };
            const newEnd = { x: boxEnd.x + dx, y: boxEnd.y + dy };
            setBoxStart(newStart);
            setBoxEnd(newEnd);
            if (!debounce) {
              emitBoxSelection(newStart, newEnd);
            }
          } else if (hasLassoSelection) {
            // Clamp delta so the entire lasso stays in bounds
            let lMinX = Number.POSITIVE_INFINITY;
            let lMaxX = Number.NEGATIVE_INFINITY;
            let lMinY = Number.POSITIVE_INFINITY;
            let lMaxY = Number.NEGATIVE_INFINITY;
            for (const p of lassoPoints) {
              if (p.x < lMinX) {
                lMinX = p.x;
              }
              if (p.x > lMaxX) {
                lMaxX = p.x;
              }
              if (p.y < lMinY) {
                lMinY = p.y;
              }
              if (p.y > lMaxY) {
                lMaxY = p.y;
              }
            }
            dx = Math.max(axLeft - lMinX, Math.min(axRight - lMaxX, dx));
            dy = Math.max(axTop - lMinY, Math.min(axBottom - lMaxY, dy));
            setLassoPoints((prev) =>
              prev.map((p) => ({ x: p.x + dx, y: p.y + dy })),
            );
            if (!debounce) {
              // Emit the shifted lasso points
              const shifted = lassoPoints.map((p) => ({
                x: p.x + dx,
                y: p.y + dy,
              }));
              emitLassoSelection(shifted);
            }
          }
          return;
        }

        if (isDrawing) {
          const clamped = clampToAxes(pt);
          setBoxEnd(clamped);
          if (!debounce) {
            emitBoxSelection(boxStart, clamped);
          }
        }
      },
      [
        getCanvasPoint,
        isLassoing,
        isDragging,
        isDrawing,
        hasBoxSelection,
        hasLassoSelection,
        boxStart,
        boxEnd,
        lassoPoints,
        clampToAxes,
        emitBoxSelection,
        emitLassoSelection,
        debounce,
        axLeft,
        axTop,
        axRight,
        axBottom,
      ],
    );

    const handlePointerUp = useCallback(() => {
      if (isLassoing) {
        setIsLassoing(false);
        if (lassoPoints.length >= 3) {
          emitLassoSelection(lassoPoints);
        } else {
          // Degenerate lasso, clear
          setLassoPoints([]);
          clearSelection();
        }
        return;
      }

      if (isDragging) {
        setIsDragging(false);
        dragStartRef.current = null;
        if (debounce) {
          if (hasBoxSelection) {
            emitBoxSelection(boxStart, boxEnd);
          } else if (hasLassoSelection) {
            emitLassoSelection(lassoPoints);
          }
        }
        return;
      }

      if (isDrawing) {
        setIsDrawing(false);
        if (debounce) {
          emitBoxSelection(boxStart, boxEnd);
        }
      }
    }, [
      isLassoing,
      isDragging,
      isDrawing,
      debounce,
      lassoPoints,
      hasBoxSelection,
      hasLassoSelection,
      boxStart,
      boxEnd,
      emitBoxSelection,
      emitLassoSelection,
      clearSelection,
    ]);

    // Draw on canvas
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas || !loadedImage) {
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return;
      }

      // Clear and draw the base image
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(loadedImage, 0, 0, canvas.width, canvas.height);

      // Draw box selection overlay
      if (boxStart && boxEnd) {
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
      }

      // Draw lasso selection overlay
      if (lassoPoints.length >= 2) {
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
      loadedImage,
      boxStart,
      boxEnd,
      lassoPoints,
      selectionColor,
      selectionOpacity,
      strokeWidth,
    ]);

    // Restore selection from value (e.g., when re-rendered by backend)
    useEffect(() => {
      if (!value || !("has_selection" in value) || !value.has_selection) {
        return;
      }

      if (value.type === "box") {
        const sel = value.data;
        const start = dataToPixel({ x: sel.x_min, y: sel.y_min });
        const end = dataToPixel({ x: sel.x_max, y: sel.y_max });
        setBoxStart(start);
        setBoxEnd(end);
      } else if (value.type === "lasso") {
        const points = value.data.map(([vx, vy]) =>
          dataToPixel({ x: vx, y: vy }),
        );
        setLassoPoints(points);
      }
      // Only restore on mount
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
      <div className="matplotlib-container">
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
