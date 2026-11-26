/* Copyright 2026 Marimo. All rights reserved. */

// The figure widget owns the pixels. Only brush selections are synced on the
// outer model so drawing a new frame does not rerun dependent notebook cells.
async function render({ el, model, host, signal }) {
  const ref = model.get("figure_ref");
  const [view, figure] = await Promise.all([
    host.getWidget(ref),
    host.getModel(ref),
  ]);
  if (signal.aborted) {
    return;
  }
  const { brush, pan, zoom, debounce } = model.get("options");
  const frame = document.createElement("div");
  frame.className = "marimo-mpl-figure";
  frame.style.cssText = "position:relative;max-width:100%;line-height:0";
  frame.style.width = figure.get("css_width");
  const mount = document.createElement("div");
  frame.append(mount);
  el.append(frame);
  // Marimo owns these gestures. The child only needs to receive resize and frame events.
  mount.inert = true;
  await view.render({ el: mount, signal });
  if (signal.aborted || !(brush || pan || zoom)) {
    return;
  }

  let brushing = Boolean(brush);
  let pending = [];
  let scheduled = false;
  async function flush() {
    if (signal.aborted) {
      return;
    }
    const gestures = pending;
    pending = [];
    try {
      await figure.send({ gestures });
    } finally {
      if (pending.length && !signal.aborted) {
        requestAnimationFrame(flush);
      } else {
        scheduled = false;
      }
    }
  }
  function navigate(command) {
    pending.push(command);
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(flush);
    }
  }
  const root = document.createElement("div");
  const container = document.createElement("div");
  root.append(container);
  frame.append(root);
  let renderer;
  function sync() {
    const width = Number.parseFloat(figure.get("css_width"));
    const height = Number.parseFloat(figure.get("css_height"));
    const value = model.get("selection");
    const panel = figure.get("geometry");
    const [left, top, right, bottom] = panel.rect;
    // Leave a pixel around the axes for the outside half of the brush stroke.
    const w = (right - left) * width + 2;
    const h = (bottom - top) * height + 2;
    const state = {
      width: w,
      height: h,
      brush,
      pan,
      zoom,
      debounce,
      selectionColor: "#3b82f6",
      selectionOpacity: 0.15,
      strokeWidth: 2,
      xBounds: panel.x,
      yBounds: panel.y,
      xScale: panel.xScale,
      yScale: panel.yScale,
      axesPixelBounds: [1, 1, w - 1, h - 1],
      dragMode: brushing ? "brush" : "pan",
      navigate,
      value,
      setValue(selection) {
        model.set("selection", selection);
      },
    };
    if (renderer) {
      renderer.update(state);
    } else {
      renderer = new BrushOverlay(container, { state, signal });
    }
    Object.assign(root.style, {
      position: "absolute",
      left: `${(left - 1 / width) * 100}%`,
      top: `${(top - 1 / height) * 100}%`,
      width: `${(w / width) * 100}%`,
      height: `${(h / height) * 100}%`,
    });
  }
  figure.on("change:geometry", sync);
  model.on("change:selection", sync);
  sync();
  if (!(pan || zoom)) {
    return;
  }

  const controls = document.createElement("div");
  controls.className = "marimo-mpl-controls";
  controls.setAttribute("role", "group");
  controls.setAttribute("aria-label", "Plot controls");
  controls.style.maxWidth = frame.style.width;
  function button(label, icon, click) {
    const button = document.createElement("button");
    button.type = "button";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">${
      icon
    }</svg>`;
    button.addEventListener("click", click, { signal });
    controls.append(button);
    return button;
  }
  if (brush && pan) {
    const toggle = (next) => {
      brushing = next;
      select.setAttribute("aria-pressed", String(next));
      hand.setAttribute("aria-pressed", String(!next));
      sync();
    };
    const select = button(
      "Brush",
      '<rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="4 2"/>',
      () => toggle(true),
    );
    const hand = button(
      "Pan",
      '<path d="M8 13V6a1.5 1.5 0 0 1 3 0v5-7a1.5 1.5 0 0 1 3 0v7-6a1.5 1.5 0 0 1 3 0v6-4a1.5 1.5 0 0 1 3 0v8a7 7 0 0 1-12 5l-5-6a1.5 1.5 0 0 1 2-2l3 2z"/>',
      () => toggle(false),
    );
    if (brush === true) {
      select.title = "Brush (Shift-drag for lasso)";
    }
    const divider = document.createElement("span");
    divider.setAttribute("role", "separator");
    divider.setAttribute("aria-orientation", "vertical");
    controls.append(divider);
    toggle(true);
  }
  button("Reset view", '<path d="M3 12a9 9 0 1 1 3 6.7M3 4v8h8"/>', () =>
    navigate({ navigation: "reset" }),
  );
  el.append(controls);
}
// A save resolves when marimo has queued the update. While it is in flight,
// the model holds the latest selection, shared by every view of this plot.
function initialize({ model, signal }) {
  let dirty = false;
  let saving = false;
  model.on("change:selection", async () => {
    dirty = true;
    if (saving) {
      return;
    }
    saving = true;
    try {
      while (dirty && !signal.aborted) {
        await new Promise(requestAnimationFrame);
        if (signal.aborted) {
          return;
        }
        dirty = false;
        await model.save_changes();
      }
    } finally {
      saving = false;
    }
  });
}

export default { initialize, render };

const HANDLE_SIZE = 7; // pixels from edge to trigger resize

const RESIZE_CURSORS = {
  n: "ns-resize",
  s: "ns-resize",
  e: "ew-resize",
  w: "ew-resize",
  nw: "nwse-resize",
  se: "nwse-resize",
  ne: "nesw-resize",
  sw: "nesw-resize",
};

function getResizeHandle(pt, boxStart, boxEnd, brush) {
  const minX = Math.min(boxStart.x, boxEnd.x);
  const maxX = Math.max(boxStart.x, boxEnd.x);
  const minY = Math.min(boxStart.y, boxEnd.y);
  const maxY = Math.max(boxStart.y, boxEnd.y);

  const nearLeft = brush !== "y" && Math.abs(pt.x - minX) <= HANDLE_SIZE;
  const nearRight = brush !== "y" && Math.abs(pt.x - maxX) <= HANDLE_SIZE;
  const nearTop = brush !== "x" && Math.abs(pt.y - minY) <= HANDLE_SIZE;
  const nearBottom = brush !== "x" && Math.abs(pt.y - maxY) <= HANDLE_SIZE;
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

function getResizeConfig(handle, start, end) {
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

function wheelPixels(delta, mode, pageSize) {
  switch (mode) {
    case WheelEvent.DOM_DELTA_LINE:
      return delta * 16;
    case WheelEvent.DOM_DELTA_PAGE:
      return delta * pageSize;
    default:
      return delta;
  }
}

function createScale(type, bounds) {
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
function pointInPolygon(pt, polygon) {
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

function pixelToData(px, g) {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  const fracX = (px.x - axLeft) / (axRight - axLeft);
  const fracY = (px.y - axTop) / (axBottom - axTop);
  const sx = createScale(g.xScale, g.xBounds);
  const sy = createScale(g.yScale, g.yBounds);
  return { x: sx.invert(fracX), y: sy.invert(1 - fracY) };
}

function dataToPixel(data, g) {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  const sx = createScale(g.xScale, g.xBounds);
  const sy = createScale(g.yScale, g.yBounds);
  return {
    x: axLeft + sx.normalize(data.x) * (axRight - axLeft),
    y: axTop + (1 - sy.normalize(data.y)) * (axBottom - axTop),
  };
}

function clampToAxes(pt, g) {
  const [axLeft, axTop, axRight, axBottom] = g.axesPixelBounds;
  return {
    x: Math.max(axLeft, Math.min(axRight, pt.x)),
    y: Math.max(axTop, Math.min(axBottom, pt.y)),
  };
}

function isPointInBox(pt, boxStart, boxEnd) {
  const minX = Math.min(boxStart.x, boxEnd.x);
  const maxX = Math.max(boxStart.x, boxEnd.x);
  const minY = Math.min(boxStart.y, boxEnd.y);
  const maxY = Math.max(boxStart.y, boxEnd.y);
  return pt.x >= minX && pt.x <= maxX && pt.y >= minY && pt.y <= maxY;
}

function isInAxes(pt, g) {
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

/** Draws and edits a selection in one subplot's coordinate system. */
export class BrushOverlay {
  #surface = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  #shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
  #state;
  #panDrag;
  #interaction = { type: "idle" };
  constructor(container, options) {
    this.#state = options.state;
    const surface = this.#surface;
    surface.classList.add(
      "block",
      "cursor-crosshair",
      "select-none",
      "outline-hidden",
    );
    surface.tabIndex = -1;
    surface.setAttribute("role", "application");
    surface.setAttribute("aria-label", "Plot gestures");
    surface.style.cssText =
      "display:block;width:100%;height:auto;touch-action:none";
    this.#shape.setAttribute("fill-rule", "evenodd");
    surface.append(this.#shape);
    container.append(surface);
    this.#setStyle();

    surface.addEventListener("pointerdown", this.#handlePointerDown, {
      signal: options.signal,
    });
    surface.addEventListener("pointermove", this.#handlePointerMove, {
      signal: options.signal,
    });
    surface.addEventListener("pointerup", this.#handlePointerUp, {
      signal: options.signal,
    });
    if (options.state.pan || options.state.zoom) {
      surface.addEventListener("wheel", this.#handleWheel, {
        passive: false,
        signal: options.signal,
      });
      surface.addEventListener(
        "lostpointercapture",
        (event) => {
          if (event.pointerId === this.#panDrag?.pointerId) {
            this.#panDrag = undefined;
          }
        },
        { signal: options.signal },
      );
    }
    surface.addEventListener("keydown", this.#handleKeyDown, {
      signal: options.signal,
    });

    options.signal.addEventListener("abort", () => surface.remove(), {
      once: true,
    });
    this.#restoreSelection(this.#state.value);
  }

  #setStyle() {
    const { width, height, selectionColor, selectionOpacity, strokeWidth } =
      this.#state;
    this.#surface.setAttribute("viewBox", `0 0 ${width} ${height}`);
    this.#shape.setAttribute("stroke", selectionColor);
    this.#shape.setAttribute("fill", selectionColor);
    this.#shape.setAttribute("fill-opacity", String(selectionOpacity));
    this.#shape.setAttribute("stroke-width", String(strokeWidth));
  }

  update(state) {
    this.#state = state;
    this.#setStyle();
    if (this.#interaction.type === "idle" || !this.#interaction.action) {
      this.#restoreSelection(state.value);
    }
  }

  #draw() {
    const selection = this.#interaction;
    if (selection.type === "box") {
      const { start, end } = selection;
      this.#shape.setAttribute(
        "d",
        `M${start.x} ${start.y} H${end.x} V${end.y} H${start.x} Z`,
      );
    } else if (selection.type === "lasso" && selection.points.length > 1) {
      const vertices = selection.points.map((p) => `${p.x},${p.y}`).join(" ");
      this.#shape.setAttribute("d", `M${vertices} Z`);
    } else {
      this.#shape.removeAttribute("d");
    }
  }

  #getPoint = (e, rect = this.#surface.getBoundingClientRect()) => {
    const scaleX = this.#state.width / rect.width;
    const scaleY = this.#state.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  #emitBoxSelection = (start, end) => {
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

  #emitLassoSelection = (points) => {
    if (points.length >= 3) {
      const data = points.map((p) => {
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

  #clearSelection = () => {
    this.#interaction = { type: "idle" };
    this.#state.setValue({ has_selection: false });
    this.#draw();
  };

  #isPointInSelection = (pt) => {
    const ix = this.#interaction;
    if (ix.type === "box") {
      return isPointInBox(pt, ix.start, ix.end);
    }
    if (ix.type === "lasso") {
      return pointInPolygon(pt, ix.points);
    }
    return false;
  };

  #constrainBox(start, end) {
    const [left, top, right, bottom] = this.#state.axesPixelBounds;
    if (this.#state.brush === "x") {
      start.y = top;
      end.y = bottom;
    } else if (this.#state.brush === "y") {
      start.x = left;
      end.x = right;
    }
  }

  #updateCursor = (pt) => {
    if (!isInAxes(pt, this.#state)) {
      this.#surface.style.cursor = "default";
      return;
    }

    const ix = this.#interaction;

    // Resize handles on idle box selection
    if (ix.type === "box" && ix.action === null) {
      const handle = getResizeHandle(pt, ix.start, ix.end, this.#state.brush);
      if (handle) {
        this.#surface.style.cursor = RESIZE_CURSORS[handle];
        return;
      }
    }

    if (this.#isPointInSelection(pt)) {
      this.#surface.style.cursor = "move";
      return;
    }

    this.#surface.style.cursor = "crosshair";
  };

  #restoreSelection = (value) => {
    if (!value || !("has_selection" in value) || !value.has_selection) {
      if (this.#interaction.type !== "idle") {
        this.#interaction = { type: "idle" };
        this.#draw();
      }
      return;
    }

    if (value.type === "box") {
      const sel = value.data;
      const start = dataToPixel({ x: sel.x_min, y: sel.y_min }, this.#state);
      const end = dataToPixel({ x: sel.x_max, y: sel.y_max }, this.#state);
      this.#constrainBox(start, end);
      this.#interaction = { type: "box", start, end, action: null };
    } else if (value.type === "lasso") {
      const points = value.data.map(([vx, vy]) =>
        dataToPixel({ x: vx, y: vy }, this.#state),
      );
      this.#interaction = { type: "lasso", points, action: null };
    }
    this.#draw();
  };

  #panTo(pointerId, point) {
    const drag = this.#panDrag;
    if (!drag || drag.pointerId !== pointerId) {
      return;
    }
    const x = (point.x - drag.last.x) / drag.width;
    const y = (drag.last.y - point.y) / drag.height;
    if (x || y) {
      this.#state.navigate?.({ navigation: "pan", x, y });
    }
    drag.last = point;
  }

  #handleWheel = (event) => {
    const { navigate, pan, zoom, axesPixelBounds, width } = this.#state;
    if (!navigate || this.#panDrag || event.buttons) {
      return;
    }

    const rect = this.#surface.getBoundingClientRect();
    const point = this.#getPoint(event, rect);
    if (!isInAxes(point, this.#state)) {
      return;
    }

    const [left, top, right, bottom] = axesPixelBounds;
    const { deltaMode, deltaX, deltaY } = event;
    let command;
    if (Math.abs(deltaX) > Math.abs(deltaY)) {
      if (pan !== "x") {
        return;
      }
      const axesWidth = ((right - left) / width) * rect.width;
      const x = -wheelPixels(deltaX, deltaMode, rect.width) / axesWidth;
      command = { navigation: "pan", x, y: 0 };
    } else {
      if (!zoom || deltaY === 0) {
        return;
      }
      const delta = wheelPixels(deltaY, deltaMode, rect.height);
      const factor = Math.exp(Math.max(-1, Math.min(1, delta * 0.002)));
      const x = (point.x - left) / (right - left);
      const y = (bottom - point.y) / (bottom - top);
      command = { navigation: "zoom", x, y, factor };
    }

    event.preventDefault();
    navigate(command);
  };

  #handlePointerDown = (e) => {
    const pt = this.#getPoint(e);
    if (this.#state.dragMode === "pan") {
      if (
        !this.#state.pan ||
        !isInAxes(pt, this.#state) ||
        e.button !== 0 ||
        this.#panDrag
      ) {
        return;
      }
      const [left, top, right, bottom] = this.#state.axesPixelBounds;
      this.#panDrag = {
        pointerId: e.pointerId,
        last: pt,
        width: right - left,
        height: bottom - top,
      };
      this.#surface.setPointerCapture(e.pointerId);
      this.#surface.style.cursor = "grabbing";
      return;
    }
    if (this.#state.brush === false) {
      return;
    }
    this.#surface.setPointerCapture(e.pointerId);
    this.#surface.focus();
    const ix = this.#interaction;

    // Shift+click -> start lasso
    if (e.shiftKey && this.#state.brush !== "x" && this.#state.brush !== "y") {
      if (!isInAxes(pt, this.#state)) {
        return;
      }
      this.#interaction = {
        type: "lasso",
        points: [clampToAxes(pt, this.#state)],
        action: { type: "drawing" },
      };
      this.#draw();
      return;
    }

    // Box exists + near edge/corner -> start resize
    if (ix.type === "box" && ix.action === null) {
      const handle = getResizeHandle(pt, ix.start, ix.end, this.#state.brush);
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
    if (this.#isPointInSelection(pt)) {
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
    if (this.#interaction.type !== "idle") {
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
    this.#draw();
  };

  #handlePointerMove = (e) => {
    const pt = this.#getPoint(e);
    if (this.#panDrag) {
      this.#panTo(e.pointerId, pt);
      return;
    }
    if (this.#state.dragMode === "pan") {
      this.#surface.style.cursor =
        this.#state.pan && isInAxes(pt, this.#state) ? "grab" : "default";
      return;
    }
    if (this.#state.brush === false) {
      return;
    }
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
      this.#draw();
      return;
    }

    // Box drawing: update end point
    if (ix.type === "box" && ix.action.type === "drawing") {
      const clamped = clampToAxes(pt, s);
      ix.end = clamped;
      this.#constrainBox(ix.start, ix.end);
      this.#draw();
      if (!s.debounce) {
        this.#emitBoxSelection(ix.start, ix.end);
      }
      return;
    }

    // Box resizing: recompute box from anchor + clamped mouse
    if (ix.type === "box" && ix.action.type === "resizing") {
      const clamped = clampToAxes(pt, s);
      const { anchor, lockX, lockY } = ix.action;
      ix.start = anchor;
      ix.end = { x: lockX ?? clamped.x, y: lockY ?? clamped.y };
      this.#constrainBox(ix.start, ix.end);
      this.#draw();
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
      this.#draw();
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
      this.#draw();
      if (!s.debounce) {
        this.#emitLassoSelection(ix.points);
      }
    }
  };

  #handlePointerUp = (e) => {
    if (!this.#surface.hasPointerCapture(e.pointerId)) {
      return;
    }
    this.#surface.releasePointerCapture(e.pointerId);
    if (this.#panDrag) {
      this.#panTo(e.pointerId, this.#getPoint(e));
      this.#panDrag = undefined;
      this.#surface.style.cursor = "grab";
      return;
    }

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
      this.#draw();
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

  #handleKeyDown = (e) => {
    if (e.key === "Escape") {
      const ix = this.#interaction;
      if (ix.type === "idle") {
        return;
      }

      // During initial drawing -> cancel without emitting
      if (ix.action?.type === "drawing") {
        this.#interaction = { type: "idle" };
        this.#draw();
      } else {
        // Completed selection, dragging, or resizing -> clear
        this.#clearSelection();
      }
    }
  };
}
