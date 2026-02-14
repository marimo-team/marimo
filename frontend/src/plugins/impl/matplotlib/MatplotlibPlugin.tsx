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

interface BoxSelection {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
}

type T =
  | {
      mode: "box";
      has_selection: boolean;
      selection: BoxSelection;
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
    selectionColor: z.string(),
    selectionOpacity: z.number(),
    strokeWidth: z.number(),
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
    // Store the loaded image as state (not a ref + boolean) so that the canvas
    // drawing effect always re-runs when the image changes.  A new Image()
    // is always a new object reference, which guarantees React sees a change
    // even if img.onload fires synchronously for data-URLs.
    const [loadedImage, setLoadedImage] = useState<HTMLImageElement | null>(
      null,
    );

    // Selection state in pixel coordinates
    const [isDrawing, setIsDrawing] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const dragStartRef = useRef<PixelPoint | null>(null);

    // Box selection: start and end in pixels
    const [boxStart, setBoxStart] = useState<PixelPoint | null>(null);
    const [boxEnd, setBoxEnd] = useState<PixelPoint | null>(null);

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

    // Emit the current box selection as a value
    const emitSelection = useCallback(
      (bStart: PixelPoint | null, bEnd: PixelPoint | null) => {
        if (bStart && bEnd) {
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
        }
      },
      [pixelToData, setValue],
    );

    // Clear selection
    const clearSelection = useCallback(() => {
      setBoxStart(null);
      setBoxEnd(null);
      setValue(undefined);
    }, [setValue]);

    // Check if a pixel point is inside the current box selection
    const isPointInSelection = useCallback(
      (pt: PixelPoint): boolean => {
        if (boxStart && boxEnd) {
          const minX = Math.min(boxStart.x, boxEnd.x);
          const maxX = Math.max(boxStart.x, boxEnd.x);
          const minY = Math.min(boxStart.y, boxEnd.y);
          const maxY = Math.max(boxStart.y, boxEnd.y);
          return pt.x >= minX && pt.x <= maxX && pt.y >= minY && pt.y <= maxY;
        }
        return false;
      },
      [boxStart, boxEnd],
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
    const hasSelection = boxStart !== null && boxEnd !== null;

    // Mouse/touch handlers
    const handlePointerDown = useCallback(
      (e: React.MouseEvent | React.TouchEvent) => {
        const pt = getCanvasPoint(e);

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
        hasSelection,
        isPointInSelection,
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

          if (boxStart && boxEnd) {
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
              emitSelection(newStart, newEnd);
            }
          }
          return;
        }

        if (isDrawing) {
          const clamped = clampToAxes(pt);
          setBoxEnd(clamped);
          if (!debounce) {
            emitSelection(boxStart, clamped);
          }
        }
      },
      [
        getCanvasPoint,
        isDragging,
        isDrawing,
        boxStart,
        boxEnd,
        clampToAxes,
        emitSelection,
        debounce,
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
        if (debounce) {
          emitSelection(boxStart, boxEnd);
        }
        return;
      }

      if (isDrawing) {
        setIsDrawing(false);
        if (debounce) {
          emitSelection(boxStart, boxEnd);
        }
      }
    }, [isDragging, isDrawing, debounce, emitSelection, boxStart, boxEnd]);

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
    }, [
      loadedImage,
      boxStart,
      boxEnd,
      selectionColor,
      selectionOpacity,
      strokeWidth,
    ]);

    // Restore selection from value (e.g., when re-rendered by backend)
    useEffect(() => {
      if (!value || !value.has_selection) {
        return;
      }

      if ("x_min" in value.selection) {
        const sel = value.selection;
        const start = dataToPixel({ x: sel.x_min, y: sel.y_min });
        const end = dataToPixel({ x: sel.x_max, y: sel.y_max });
        setBoxStart(start);
        setBoxEnd(end);
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
