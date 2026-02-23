/* Copyright 2026 Marimo. All rights reserved. */

import type { Setter } from "@/plugins/types";

export type ScaleType = "linear" | "log";

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
  xScale: ScaleType;
  yScale: ScaleType;
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

// -- State machine types --

type BoxAction =
  | { type: "drawing" }
  | { type: "dragging"; origin: PixelPoint }
  | {
      type: "resizing";
      anchor: PixelPoint;
      lockX: number | null;
      lockY: number | null;
    };

type LassoAction =
  | { type: "drawing" }
  | { type: "dragging"; origin: PixelPoint };

type Interaction =
  | { type: "idle" }
  | {
      type: "box";
      start: PixelPoint;
      end: PixelPoint;
      action: BoxAction | null;
    }
  | { type: "lasso"; points: PixelPoint[]; action: LassoAction | null };

// -- Resize handle detection --

type ResizeHandle = "n" | "s" | "e" | "w" | "nw" | "ne" | "sw" | "se";

const HANDLE_SIZE = 7; // pixels from edge to trigger resize

const RESIZE_CURSORS: Record<ResizeHandle, string> = {
  n: "ns-resize",
  s: "ns-resize",
  e: "ew-resize",
  w: "ew-resize",
  nw: "nwse-resize",
  se: "nwse-resize",
  ne: "nesw-resize",
  sw: "nesw-resize",
};

function getResizeHandle(
  pt: PixelPoint,
  boxStart: PixelPoint,
  boxEnd: PixelPoint,
): ResizeHandle | null {
  const minX = Math.min(boxStart.x, boxEnd.x);
  const maxX = Math.max(boxStart.x, boxEnd.x);
  const minY = Math.min(boxStart.y, boxEnd.y);
  const maxY = Math.max(boxStart.y, boxEnd.y);

  const nearLeft = Math.abs(pt.x - minX) <= HANDLE_SIZE;
  const nearRight = Math.abs(pt.x - maxX) <= HANDLE_SIZE;
  const nearTop = Math.abs(pt.y - minY) <= HANDLE_SIZE;
  const nearBottom = Math.abs(pt.y - maxY) <= HANDLE_SIZE;
  const withinX = pt.x >= minX - HANDLE_SIZE && pt.x <= maxX + HANDLE_SIZE;
  const withinY = pt.y >= minY - HANDLE_SIZE && pt.y <= maxY + HANDLE_SIZE;

  // Corners first (more specific)
  if (nearLeft && nearTop) {
    return "nw";
  }
  if (nearRight && nearTop) {
    return "ne";
  }
  if (nearLeft && nearBottom) {
    return "sw";
  }
  if (nearRight && nearBottom) {
    return "se";
  }

  // Edges
  if (nearTop && withinX) {
    return "n";
  }
  if (nearBottom && withinX) {
    return "s";
  }
  if (nearLeft && withinY) {
    return "w";
  }
  if (nearRight && withinY) {
    return "e";
  }

  return null;
}

function getResizeConfig(
  handle: ResizeHandle,
  start: PixelPoint,
  end: PixelPoint,
): { anchor: PixelPoint; lockX: number | null; lockY: number | null } {
  const minX = Math.min(start.x, end.x);
  const maxX = Math.max(start.x, end.x);
  const minY = Math.min(start.y, end.y);
  const maxY = Math.max(start.y, end.y);

  switch (handle) {
    case "nw":
      return { anchor: { x: maxX, y: maxY }, lockX: null, lockY: null };
    case "ne":
      return { anchor: { x: minX, y: maxY }, lockX: null, lockY: null };
    case "sw":
      return { anchor: { x: maxX, y: minY }, lockX: null, lockY: null };
    case "se":
      return { anchor: { x: minX, y: minY }, lockX: null, lockY: null };
    case "n":
      return { anchor: { x: minX, y: maxY }, lockX: maxX, lockY: null };
    case "s":
      return { anchor: { x: minX, y: minY }, lockX: maxX, lockY: null };
    case "w":
      return { anchor: { x: maxX, y: minY }, lockX: null, lockY: maxY };
    case "e":
      return { anchor: { x: minX, y: minY }, lockX: null, lockY: maxY };
  }
}

export interface MatplotlibState extends Data {
  value: SelectionValue;
  setValue: Setter<SelectionValue>;
}

// Minimal d3-like scale: maps between data domain and [0, 1] fraction
interface Scale {
  /** data value → normalized [0, 1] */
  normalize(value: number): number;
  /** normalized [0, 1] → data value */
  invert(frac: number): number;
}

function createScale(type: ScaleType, bounds: [number, number]): Scale {
  const [min, max] = bounds;
  if (type === "log") {
    const logMin = Math.log10(min);
    const logRange = Math.log10(max) - logMin;
    return {
      normalize: (v) => (Math.log10(v) - logMin) / logRange,
      invert: (f) => 10 ** (logMin + f * logRange),
    };
  }
  const range = max - min;
  return {
    normalize: (v) => (v - min) / range,
    invert: (f) => min + f * range,
  };
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
  const fracX = (px.x - axLeft) / (axRight - axLeft);
  const fracY = (px.y - axTop) / (axBottom - axTop);
  const sx = createScale(g.xScale, g.xBounds);
  const sy = createScale(g.yScale, g.yBounds);
  return { x: sx.invert(fracX), y: sy.invert(1 - fracY) };
}

function dataToPixel(data: DataPoint, g: AxesGeometry): PixelPoint {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  const sx = createScale(g.xScale, g.xBounds);
  const sy = createScale(g.yScale, g.yBounds);
  return {
    x: axLeft + sx.normalize(data.x) * (axRight - axLeft),
    y: axTop + (1 - sy.normalize(data.y)) * (axBottom - axTop),
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

function isInAxes(pt: PixelPoint, g: AxesGeometry): boolean {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  return pt.x >= axLeft && pt.x <= axRight && pt.y >= axTop && pt.y <= axBottom;
}

export const visibleForTesting = {
  createScale,
  pixelToData,
  dataToPixel,
  pointInPolygon,
  clampToAxes,
  isPointInBox,
  isInAxes,
};

export class MatplotlibRenderer {
  #canvas: HTMLCanvasElement;
  #container: HTMLDivElement;
  #state: MatplotlibState;
  #interaction: Interaction = { type: "idle" };
  #rafId = 0;
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
    const dpr = globalThis.devicePixelRatio ?? 1;
    canvas.width = this.#state.width * dpr;
    canvas.height = this.#state.height * dpr;
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
      cancelAnimationFrame(this.#rafId);
      this.#canvas.remove();
    });

    // Initial load
    this.#loadImage(this.#state.chartBase64);
    this.#restoreSelection(this.#state.value);
  }

  update(state: MatplotlibState): void {
    const prev = this.#state;
    this.#state = state;

    let needsRedraw = false;

    // Update canvas dimensions if changed
    if (state.width !== prev.width || state.height !== prev.height) {
      const dpr = globalThis.devicePixelRatio ?? 1;
      this.#canvas.width = state.width * dpr;
      this.#canvas.height = state.height * dpr;
      this.#canvas.style.width = `${state.width}px`;
      this.#canvas.style.height = `${state.height}px`;
      needsRedraw = true;
    }

    if (state.chartBase64 !== this.#currentChartBase64) {
      this.#loadImage(state.chartBase64);
      return;
    }

    // Redraw if style props changed or dimensions changed
    if (
      needsRedraw ||
      state.selectionColor !== prev.selectionColor ||
      state.selectionOpacity !== prev.selectionOpacity ||
      state.strokeWidth !== prev.strokeWidth
    ) {
      this.#drawCanvas();
    }
  }

  #loadImage(chartBase64: string): void {
    this.#currentChartBase64 = chartBase64;
    this.#imageGeneration++;
    const generation = this.#imageGeneration;

    // Clear selection on new chart
    this.#interaction = { type: "idle" };

    // Clear stale image so old content doesn't linger while new image loads
    this.#image = null;
    const ctx = this.#canvas.getContext("2d");
    if (ctx) {
      const dpr = globalThis.devicePixelRatio ?? 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, this.#state.width, this.#state.height);
    }

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

    // Scale for HiDPI: all coordinates remain in logical pixels
    const dpr = globalThis.devicePixelRatio ?? 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Clear and draw the base image
    ctx.clearRect(0, 0, s.width, s.height);
    ctx.drawImage(img, 0, 0, s.width, s.height);

    // Draw box selection overlay
    if (ix.type === "box") {
      const x = Math.min(ix.start.x, ix.end.x);
      const y = Math.min(ix.start.y, ix.end.y);
      const w = Math.abs(ix.end.x - ix.start.x);
      const h = Math.abs(ix.end.y - ix.start.y);

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
    if (ix.type === "lasso" && ix.points.length >= 2) {
      ctx.beginPath();
      ctx.moveTo(ix.points[0].x, ix.points[0].y);
      for (let i = 1; i < ix.points.length; i++) {
        ctx.lineTo(ix.points[i].x, ix.points[i].y);
      }
      ctx.closePath();

      ctx.save();
      ctx.fillStyle = s.selectionColor;
      ctx.globalAlpha = s.selectionOpacity;
      ctx.fill("evenodd");
      ctx.restore();

      ctx.strokeStyle = s.selectionColor;
      ctx.lineWidth = s.strokeWidth;
      ctx.stroke();
    }
  };

  #scheduleRedraw = (): void => {
    cancelAnimationFrame(this.#rafId);
    this.#rafId = requestAnimationFrame(this.#drawCanvas);
  };

  #getCanvasPoint = (e: PointerEvent): PixelPoint => {
    const rect = this.#canvas.getBoundingClientRect();
    const scaleX = this.#state.width / rect.width;
    const scaleY = this.#state.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  #emitBoxSelection = (start: PixelPoint, end: PixelPoint): void => {
    const d1 = pixelToData(start, this.#state);
    const d2 = pixelToData(end, this.#state);
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
    this.#interaction = { type: "idle" };
    this.#state.setValue({ has_selection: false });
    this.#scheduleRedraw();
  };

  #hasSelection = (): boolean => {
    return this.#interaction.type !== "idle";
  };

  #isPointInSelection = (pt: PixelPoint): boolean => {
    const ix = this.#interaction;
    if (ix.type === "box") {
      return isPointInBox(pt, ix.start, ix.end);
    }
    if (ix.type === "lasso") {
      return pointInPolygon(pt, ix.points);
    }
    return false;
  };

  #updateCursor = (pt: PixelPoint): void => {
    const [axLeft, axTop, axRight, axBottom] = this.#state.axesPixelBounds;
    const inAxes =
      pt.x >= axLeft && pt.x <= axRight && pt.y >= axTop && pt.y <= axBottom;

    if (!inAxes) {
      this.#canvas.style.cursor = "default";
      return;
    }

    const ix = this.#interaction;

    // Resize handles on idle box selection
    if (ix.type === "box" && ix.action === null) {
      const handle = getResizeHandle(pt, ix.start, ix.end);
      if (handle) {
        this.#canvas.style.cursor = RESIZE_CURSORS[handle];
        return;
      }
    }

    if (this.#hasSelection() && this.#isPointInSelection(pt)) {
      this.#canvas.style.cursor = "move";
      return;
    }

    this.#canvas.style.cursor = "crosshair";
  };

  #restoreSelection = (value: SelectionValue): void => {
    if (!value || !("has_selection" in value) || !value.has_selection) {
      return;
    }

    if (value.type === "box") {
      const sel = value.data;
      const start = dataToPixel({ x: sel.x_min, y: sel.y_min }, this.#state);
      const end = dataToPixel({ x: sel.x_max, y: sel.y_max }, this.#state);
      this.#interaction = { type: "box", start, end, action: null };
    } else if (value.type === "lasso") {
      const points = value.data.map(([vx, vy]) =>
        dataToPixel({ x: vx, y: vy }, this.#state),
      );
      this.#interaction = { type: "lasso", points, action: null };
    }
    this.#scheduleRedraw();
  };

  #handlePointerDown = (e: PointerEvent): void => {
    this.#canvas.setPointerCapture(e.pointerId);
    this.#container.focus();
    const pt = this.#getCanvasPoint(e);
    const ix = this.#interaction;

    // Shift+click -> start lasso
    if (e.shiftKey) {
      if (!isInAxes(pt, this.#state)) {
        return;
      }
      this.#interaction = {
        type: "lasso",
        points: [clampToAxes(pt, this.#state)],
        action: { type: "drawing" },
      };
      this.#scheduleRedraw();
      return;
    }

    // Box exists + near edge/corner -> start resize
    if (ix.type === "box" && ix.action === null) {
      const handle = getResizeHandle(pt, ix.start, ix.end);
      if (handle) {
        const { anchor, lockX, lockY } = getResizeConfig(
          handle,
          ix.start,
          ix.end,
        );
        this.#interaction = {
          type: "box",
          start: ix.start,
          end: ix.end,
          action: { type: "resizing", anchor, lockX, lockY },
        };
        return;
      }
    }

    // Inside existing selection -> start drag
    if (this.#hasSelection() && this.#isPointInSelection(pt)) {
      if (ix.type === "box") {
        this.#interaction = {
          type: "box",
          start: ix.start,
          end: ix.end,
          action: { type: "dragging", origin: pt },
        };
      } else if (ix.type === "lasso") {
        this.#interaction = {
          type: "lasso",
          points: ix.points,
          action: { type: "dragging", origin: pt },
        };
      }
      return;
    }

    // Outside selection with existing one -> clear, then start new box
    if (this.#hasSelection()) {
      this.#clearSelection();
    }

    // Start new box selection (only inside axes)
    if (!isInAxes(pt, this.#state)) {
      return;
    }
    const clamped = clampToAxes(pt, this.#state);
    this.#interaction = {
      type: "box",
      start: clamped,
      end: clamped,
      action: { type: "drawing" },
    };
    this.#scheduleRedraw();
  };

  #handlePointerMove = (e: PointerEvent): void => {
    const pt = this.#getCanvasPoint(e);
    const ix = this.#interaction;
    const s = this.#state;

    // No active action -> just update cursor
    if (ix.type === "idle" || ix.action === null) {
      this.#updateCursor(pt);
      return;
    }

    // Lasso drawing: append clamped point
    if (ix.type === "lasso" && ix.action.type === "drawing") {
      ix.points.push(clampToAxes(pt, s));
      this.#scheduleRedraw();
      return;
    }

    // Box drawing: update end point
    if (ix.type === "box" && ix.action.type === "drawing") {
      const clamped = clampToAxes(pt, s);
      ix.end = clamped;
      this.#scheduleRedraw();
      if (!s.debounce) {
        this.#emitBoxSelection(ix.start, clamped);
      }
      return;
    }

    // Box resizing: recompute box from anchor + clamped mouse
    if (ix.type === "box" && ix.action.type === "resizing") {
      const clamped = clampToAxes(pt, s);
      const { anchor, lockX, lockY } = ix.action;
      ix.start = anchor;
      ix.end = { x: lockX ?? clamped.x, y: lockY ?? clamped.y };
      this.#scheduleRedraw();
      if (!s.debounce) {
        this.#emitBoxSelection(ix.start, ix.end);
      }
      return;
    }

    // Box dragging
    if (ix.type === "box" && ix.action.type === "dragging") {
      const [axLeft, axTop, axRight, axBottom] = s.axesPixelBounds;
      let dx = pt.x - ix.action.origin.x;
      let dy = pt.y - ix.action.origin.y;
      ix.action.origin = pt;

      const minX = Math.min(ix.start.x, ix.end.x);
      const maxX = Math.max(ix.start.x, ix.end.x);
      const minY = Math.min(ix.start.y, ix.end.y);
      const maxY = Math.max(ix.start.y, ix.end.y);
      dx = Math.max(axLeft - minX, Math.min(axRight - maxX, dx));
      dy = Math.max(axTop - minY, Math.min(axBottom - maxY, dy));
      ix.start = { x: ix.start.x + dx, y: ix.start.y + dy };
      ix.end = { x: ix.end.x + dx, y: ix.end.y + dy };
      this.#scheduleRedraw();
      if (!s.debounce) {
        this.#emitBoxSelection(ix.start, ix.end);
      }
      return;
    }

    // Lasso dragging
    if (ix.type === "lasso" && ix.action.type === "dragging") {
      const [axLeft, axTop, axRight, axBottom] = s.axesPixelBounds;
      let dx = pt.x - ix.action.origin.x;
      let dy = pt.y - ix.action.origin.y;
      ix.action.origin = pt;

      let lMinX = Number.POSITIVE_INFINITY;
      let lMaxX = Number.NEGATIVE_INFINITY;
      let lMinY = Number.POSITIVE_INFINITY;
      let lMaxY = Number.NEGATIVE_INFINITY;
      for (const lp of ix.points) {
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
      for (let i = 0; i < ix.points.length; i++) {
        ix.points[i] = {
          x: ix.points[i].x + dx,
          y: ix.points[i].y + dy,
        };
      }
      this.#scheduleRedraw();
      if (!s.debounce) {
        this.#emitLassoSelection(ix.points);
      }
    }
  };

  #handlePointerUp = (e: PointerEvent): void => {
    this.#canvas.releasePointerCapture(e.pointerId);

    const ix = this.#interaction;
    const s = this.#state;

    // Lasso drawing complete
    if (ix.type === "lasso" && ix.action?.type === "drawing") {
      if (ix.points.length >= 3) {
        ix.action = null;
        this.#emitLassoSelection(ix.points);
      } else {
        this.#interaction = { type: "idle" };
        this.#state.setValue({ has_selection: false });
      }
      this.#scheduleRedraw();
      return;
    }

    // Lasso dragging complete
    if (ix.type === "lasso" && ix.action?.type === "dragging") {
      ix.action = null;
      if (s.debounce) {
        this.#emitLassoSelection(ix.points);
      }
      return;
    }

    // Box action complete (drawing, dragging, or resizing)
    if (ix.type === "box" && ix.action !== null) {
      ix.action = null;
      if (s.debounce) {
        this.#emitBoxSelection(ix.start, ix.end);
      }
    }
  };

  #handleKeyDown = (e: KeyboardEvent): void => {
    if (e.key === "Escape") {
      const ix = this.#interaction;
      if (ix.type === "idle") {
        return;
      }

      // During initial drawing -> cancel without emitting
      if (ix.action?.type === "drawing") {
        this.#interaction = { type: "idle" };
        this.#scheduleRedraw();
      } else {
        // Completed selection, dragging, or resizing -> clear
        this.#clearSelection();
      }
    }
  };
}
