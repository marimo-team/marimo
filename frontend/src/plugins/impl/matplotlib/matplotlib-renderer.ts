/* Copyright 2026 Marimo. All rights reserved. */

import type { Setter } from "@/plugins/types";

export interface Data {
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

export interface BoxData {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
}

export type SelectionValue =
  | { type: "box"; has_selection: true; data: BoxData }
  | { type: "lasso"; has_selection: true; data: [number, number][] }
  | { has_selection: false }
  | undefined;

type AxesGeometry = Pick<
  Data,
  "axesPixelBounds" | "xBounds" | "xScale" | "yBounds" | "yScale"
>;

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

export interface MatplotlibState extends Data {
  value: SelectionValue;
  setValue: Setter<SelectionValue>;
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

function pixelToData(px: PixelPoint, g: AxesGeometry): DataPoint {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  const axWidth = axRight - axLeft;
  const axHeight = axBottom - axTop;
  const fracX = (px.x - axLeft) / axWidth;
  const fracY = (px.y - axTop) / axHeight;

  let dataX: number;
  if (g.xScale === "log") {
    const logMin = Math.log10(g.xBounds[0]);
    const logMax = Math.log10(g.xBounds[1]);
    dataX = 10 ** (logMin + fracX * (logMax - logMin));
  } else {
    dataX = g.xBounds[0] + fracX * (g.xBounds[1] - g.xBounds[0]);
  }

  let dataY: number;
  if (g.yScale === "log") {
    const logMin = Math.log10(g.yBounds[0]);
    const logMax = Math.log10(g.yBounds[1]);
    dataY = 10 ** (logMax - fracY * (logMax - logMin));
  } else {
    dataY = g.yBounds[1] - fracY * (g.yBounds[1] - g.yBounds[0]);
  }

  return { x: dataX, y: dataY };
}

function dataToPixel(data: DataPoint, g: AxesGeometry): PixelPoint {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  const axWidth = axRight - axLeft;
  const axHeight = axBottom - axTop;

  let fracX: number;
  if (g.xScale === "log") {
    fracX =
      (Math.log10(data.x) - Math.log10(g.xBounds[0])) /
      (Math.log10(g.xBounds[1]) - Math.log10(g.xBounds[0]));
  } else {
    fracX = (data.x - g.xBounds[0]) / (g.xBounds[1] - g.xBounds[0]);
  }

  let fracY: number;
  if (g.yScale === "log") {
    fracY =
      (Math.log10(g.yBounds[1]) - Math.log10(data.y)) /
      (Math.log10(g.yBounds[1]) - Math.log10(g.yBounds[0]));
  } else {
    fracY = (g.yBounds[1] - data.y) / (g.yBounds[1] - g.yBounds[0]);
  }

  return {
    x: axLeft + fracX * axWidth,
    y: axTop + fracY * axHeight,
  };
}

function clampToAxes(pt: PixelPoint, g: AxesGeometry) {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  return {
    x: Math.max(axLeft, Math.min(axRight, pt.x)),
    y: Math.max(axTop, Math.min(axBottom, pt.y)),
  };
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

export class MatplotlibRenderer {
  #canvas: HTMLCanvasElement;
  #container: HTMLDivElement;
  #state: MatplotlibState;
  #interaction: InteractionState = {
    mode: "idle",
    boxStart: null,
    boxEnd: null,
    lassoPoints: [],
    dragStart: null,
    rafId: 0,
  };
  #image: HTMLImageElement | null = null;
  #imageGeneration = 0;
  #currentChartBase64 = "";

  constructor(
    container: HTMLDivElement,
    options: { state: MatplotlibState; signal: AbortSignal },
  ) {
    this.#container = container;
    this.#state = options.state;

    // Configure container
    container.tabIndex = -1;
    container.role = "application";
    container.className = "relative inline-block select-none outline-none";

    // Create canvas
    const canvas = document.createElement("canvas");
    canvas.className = "block cursor-crosshair";
    canvas.width = this.#state.width;
    canvas.height = this.#state.height;
    canvas.style.width = `${this.#state.width}px`;
    canvas.style.height = `${this.#state.height}px`;
    canvas.style.maxWidth = "100%";
    canvas.style.touchAction = "none";
    container.append(canvas);
    this.#canvas = canvas;

    // Register event listeners with AbortSignal for auto-cleanup
    canvas.addEventListener("pointerdown", this.#handlePointerDown, {
      signal: options.signal,
    });
    canvas.addEventListener("pointermove", this.#handlePointerMove, {
      signal: options.signal,
    });
    canvas.addEventListener("pointerup", this.#handlePointerUp, {
      signal: options.signal,
    });
    container.addEventListener("keydown", this.#handleKeyDown, {
      signal: options.signal,
    });

    // Clean up on abort
    options.signal.addEventListener("abort", () => {
      cancelAnimationFrame(this.#interaction.rafId);
      this.#canvas.remove();
    });

    // Initial load
    this.#loadImage(this.#state.chartBase64);
    this.#restoreSelection(this.#state.value);
  }

  update(state: MatplotlibState): void {
    const prev = this.#state;
    this.#state = state;

    if (state.chartBase64 !== this.#currentChartBase64) {
      this.#loadImage(state.chartBase64);
      return;
    }

    // Update canvas dimensions if changed
    if (state.width !== prev.width || state.height !== prev.height) {
      this.#canvas.width = state.width;
      this.#canvas.height = state.height;
      this.#canvas.style.width = `${state.width}px`;
      this.#canvas.style.height = `${state.height}px`;
    }

    // Redraw if style props changed or dimensions changed
    if (
      state.selectionColor !== prev.selectionColor ||
      state.selectionOpacity !== prev.selectionOpacity ||
      state.strokeWidth !== prev.strokeWidth ||
      state.width !== prev.width ||
      state.height !== prev.height
    ) {
      this.#drawCanvas();
    }
  }

  #loadImage(chartBase64: string): void {
    this.#currentChartBase64 = chartBase64;
    this.#imageGeneration++;
    const generation = this.#imageGeneration;

    // Clear selection on new chart
    this.#interaction.boxStart = null;
    this.#interaction.boxEnd = null;
    this.#interaction.lassoPoints = [];
    this.#interaction.mode = "idle";

    const img = new Image();
    img.onload = () => {
      if (generation !== this.#imageGeneration) {
        return;
      }
      this.#image = img;
      this.#drawCanvas();
    };
    img.src = chartBase64;
  }

  #drawCanvas = (): void => {
    const img = this.#image;
    if (!img) {
      return;
    }

    const ctx = this.#canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    const s = this.#state;
    const ix = this.#interaction;

    // Clear and draw the base image
    ctx.clearRect(0, 0, this.#canvas.width, this.#canvas.height);
    ctx.drawImage(img, 0, 0, this.#canvas.width, this.#canvas.height);

    // Draw box selection overlay
    if (ix.boxStart && ix.boxEnd) {
      const x = Math.min(ix.boxStart.x, ix.boxEnd.x);
      const y = Math.min(ix.boxStart.y, ix.boxEnd.y);
      const w = Math.abs(ix.boxEnd.x - ix.boxStart.x);
      const h = Math.abs(ix.boxEnd.y - ix.boxStart.y);

      ctx.save();
      ctx.fillStyle = s.selectionColor;
      ctx.globalAlpha = s.selectionOpacity;
      ctx.fillRect(x, y, w, h);
      ctx.restore();

      ctx.strokeStyle = s.selectionColor;
      ctx.lineWidth = s.strokeWidth;
      ctx.strokeRect(x, y, w, h);
    }

    // Draw lasso selection overlay
    if (ix.lassoPoints.length >= 2) {
      ctx.beginPath();
      ctx.moveTo(ix.lassoPoints[0].x, ix.lassoPoints[0].y);
      for (let i = 1; i < ix.lassoPoints.length; i++) {
        ctx.lineTo(ix.lassoPoints[i].x, ix.lassoPoints[i].y);
      }
      ctx.closePath();

      ctx.save();
      ctx.fillStyle = s.selectionColor;
      ctx.globalAlpha = s.selectionOpacity;
      ctx.fill();
      ctx.restore();

      ctx.strokeStyle = s.selectionColor;
      ctx.lineWidth = s.strokeWidth;
      ctx.stroke();
    }
  };

  #scheduleRedraw = (): void => {
    cancelAnimationFrame(this.#interaction.rafId);
    this.#interaction.rafId = requestAnimationFrame(this.#drawCanvas);
  };

  #getCanvasPoint = (e: PointerEvent): PixelPoint => {
    const rect = this.#canvas.getBoundingClientRect();
    const scaleX = this.#canvas.width / rect.width;
    const scaleY = this.#canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  #emitBoxSelection = (
    bStart: PixelPoint | null,
    bEnd: PixelPoint | null,
  ): void => {
    if (bStart && bEnd) {
      const d1 = pixelToData(bStart, this.#state);
      const d2 = pixelToData(bEnd, this.#state);
      this.#state.setValue({
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
  };

  #emitLassoSelection = (points: PixelPoint[]): void => {
    if (points.length >= 3) {
      const data: [number, number][] = points.map((p) => {
        const d = pixelToData(p, this.#state);
        return [d.x, d.y];
      });
      this.#state.setValue({
        type: "lasso",
        has_selection: true,
        data,
      });
    }
  };

  #clearSelection = (): void => {
    this.#interaction.boxStart = null;
    this.#interaction.boxEnd = null;
    this.#interaction.lassoPoints = [];
    this.#interaction.mode = "idle";
    this.#state.setValue({ has_selection: false });
    this.#scheduleRedraw();
  };

  #hasSelection = (): boolean => {
    const ix = this.#interaction;
    return (
      (ix.boxStart !== null && ix.boxEnd !== null) || ix.lassoPoints.length >= 3
    );
  };

  #isPointInSelection = (pt: PixelPoint): boolean => {
    const ix = this.#interaction;
    if (ix.boxStart && ix.boxEnd) {
      return isPointInBox(pt, ix.boxStart, ix.boxEnd);
    }
    if (ix.lassoPoints.length >= 3) {
      return pointInPolygon(pt, ix.lassoPoints);
    }
    return false;
  };

  #updateCursor = (pt: PixelPoint): void => {
    const [axLeft, axTop, axRight, axBottom] = this.#state.axesPixelBounds;
    const inAxes =
      pt.x >= axLeft && pt.x <= axRight && pt.y >= axTop && pt.y <= axBottom;

    if (!inAxes) {
      this.#canvas.style.cursor = "default";
    } else if (this.#hasSelection() && this.#isPointInSelection(pt)) {
      this.#canvas.style.cursor = "move";
    } else {
      this.#canvas.style.cursor = "crosshair";
    }
  };

  #restoreSelection = (value: SelectionValue): void => {
    if (!value || !("has_selection" in value) || !value.has_selection) {
      return;
    }

    if (value.type === "box") {
      const sel = value.data;
      const start = dataToPixel({ x: sel.x_min, y: sel.y_min }, this.#state);
      const end = dataToPixel({ x: sel.x_max, y: sel.y_max }, this.#state);
      this.#interaction.boxStart = start;
      this.#interaction.boxEnd = end;
      this.#interaction.lassoPoints = [];
    } else if (value.type === "lasso") {
      const points = value.data.map(([vx, vy]) =>
        dataToPixel({ x: vx, y: vy }, this.#state),
      );
      this.#interaction.lassoPoints = points;
      this.#interaction.boxStart = null;
      this.#interaction.boxEnd = null;
    }
    this.#scheduleRedraw();
  };

  #handlePointerDown = (e: PointerEvent): void => {
    this.#canvas.setPointerCapture(e.pointerId);
    this.#container.focus();
    const pt = this.#getCanvasPoint(e);
    const ix = this.#interaction;

    // Shift+click → start lasso
    if (e.shiftKey) {
      ix.boxStart = null;
      ix.boxEnd = null;
      ix.mode = "lassoing";
      ix.lassoPoints = [clampToAxes(pt, this.#state)];
      this.#scheduleRedraw();
      return;
    }

    // If clicking inside existing selection, start dragging
    if (this.#hasSelection() && this.#isPointInSelection(pt)) {
      ix.mode = "dragging";
      ix.dragStart = pt;
      return;
    }

    // If clicking outside selection with an existing one, clear it
    // then fall through to start a new box selection
    if (this.#hasSelection() && !this.#isPointInSelection(pt)) {
      this.#clearSelection();
    }

    // Start new box selection
    const clamped = clampToAxes(pt, this.#state);
    ix.mode = "drawing";
    ix.boxStart = clamped;
    ix.boxEnd = clamped;
    this.#scheduleRedraw();
  };

  #handlePointerMove = (e: PointerEvent): void => {
    const pt = this.#getCanvasPoint(e);
    const ix = this.#interaction;
    const s = this.#state;

    // Update cursor when idle
    if (ix.mode === "idle") {
      this.#updateCursor(pt);
    }

    // Lassoing: append clamped point
    if (ix.mode === "lassoing") {
      ix.lassoPoints.push(clampToAxes(pt, this.#state));
      this.#scheduleRedraw();
      return;
    }

    if (ix.mode === "dragging" && ix.dragStart) {
      const [axLeft, axTop, axRight, axBottom] = s.axesPixelBounds;
      let dx = pt.x - ix.dragStart.x;
      let dy = pt.y - ix.dragStart.y;
      ix.dragStart = pt;

      if (ix.boxStart && ix.boxEnd) {
        // Clamp delta so the entire box stays in bounds
        const minX = Math.min(ix.boxStart.x, ix.boxEnd.x);
        const maxX = Math.max(ix.boxStart.x, ix.boxEnd.x);
        const minY = Math.min(ix.boxStart.y, ix.boxEnd.y);
        const maxY = Math.max(ix.boxStart.y, ix.boxEnd.y);
        dx = Math.max(axLeft - minX, Math.min(axRight - maxX, dx));
        dy = Math.max(axTop - minY, Math.min(axBottom - maxY, dy));
        ix.boxStart = { x: ix.boxStart.x + dx, y: ix.boxStart.y + dy };
        ix.boxEnd = { x: ix.boxEnd.x + dx, y: ix.boxEnd.y + dy };
        this.#scheduleRedraw();
        if (!s.debounce) {
          this.#emitBoxSelection(ix.boxStart, ix.boxEnd);
        }
      } else if (ix.lassoPoints.length >= 3) {
        // Clamp delta so the entire lasso stays in bounds
        let lMinX = Number.POSITIVE_INFINITY;
        let lMaxX = Number.NEGATIVE_INFINITY;
        let lMinY = Number.POSITIVE_INFINITY;
        let lMaxY = Number.NEGATIVE_INFINITY;
        for (const lp of ix.lassoPoints) {
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
        dx = Math.max(axLeft - lMinX, Math.min(axRight - lMaxX, dx));
        dy = Math.max(axTop - lMinY, Math.min(axBottom - lMaxY, dy));
        for (let i = 0; i < ix.lassoPoints.length; i++) {
          ix.lassoPoints[i] = {
            x: ix.lassoPoints[i].x + dx,
            y: ix.lassoPoints[i].y + dy,
          };
        }
        this.#scheduleRedraw();
        if (!s.debounce) {
          this.#emitLassoSelection(ix.lassoPoints);
        }
      }
      return;
    }

    if (ix.mode === "drawing") {
      const clamped = clampToAxes(pt, this.#state);
      ix.boxEnd = clamped;
      this.#scheduleRedraw();
      if (!s.debounce) {
        this.#emitBoxSelection(ix.boxStart, clamped);
      }
    }
  };

  #handlePointerUp = (e: PointerEvent): void => {
    this.#canvas.releasePointerCapture(e.pointerId);

    const ix = this.#interaction;
    const s = this.#state;

    if (ix.mode === "lassoing") {
      ix.mode = "idle";
      if (ix.lassoPoints.length >= 3) {
        this.#emitLassoSelection(ix.lassoPoints);
      } else {
        // Degenerate lasso, clear
        ix.lassoPoints = [];
        this.#state.setValue({ has_selection: false });
      }
      this.#scheduleRedraw();
      return;
    }

    if (ix.mode === "dragging") {
      ix.mode = "idle";
      ix.dragStart = null;
      if (s.debounce) {
        if (ix.boxStart && ix.boxEnd) {
          this.#emitBoxSelection(ix.boxStart, ix.boxEnd);
        } else if (ix.lassoPoints.length >= 3) {
          this.#emitLassoSelection(ix.lassoPoints);
        }
      }
      return;
    }

    if (ix.mode === "drawing") {
      ix.mode = "idle";
      if (s.debounce) {
        this.#emitBoxSelection(ix.boxStart, ix.boxEnd);
      }
    }
  };

  #handleKeyDown = (e: KeyboardEvent): void => {
    if (e.key === "Escape") {
      const ix = this.#interaction;
      if (ix.mode === "drawing" || ix.mode === "lassoing") {
        ix.mode = "idle";
        ix.boxStart = null;
        ix.boxEnd = null;
        ix.lassoPoints = [];
        this.#scheduleRedraw();
      } else if (this.#hasSelection()) {
        this.#clearSelection();
      }
    }
  };
}
