/* Copyright 2026 Marimo. All rights reserved. */

import { type Extension, StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  showTooltip,
  type Tooltip,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
} from "@codemirror/view";
import { type DebouncedFunc, debounce } from "lodash-es";
import type { CellId } from "@/core/cells/ids";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import { datasetTablesAtom } from "@/core/datasets/state";
import { store } from "@/core/state/jotai";
import { storageNamespacesAtom } from "@/core/storage/state";
import { variablesAtom } from "@/core/variables/state";
import { languageAdapterState } from "../language/extension";
import { openLensTarget } from "./actions";
import { findCacheSites, findDeclarationSites } from "./analyzer";
import { type CodeLensSpec, getLensEntities } from "./entities";
import { LENS_ICONS, LENS_TOOLTIPS } from "./icons";
import { mountLensPopover } from "./popover";

// Delay (in ms) before showing the hover popover, matching the app's
// tooltip delay
export const CODE_LENS_HOVER_DELAY_MS = 400;
// Grace period (in ms) after the pointer leaves the icon (or the popover)
// before hiding, so the pointer can travel from the icon into the popover
// without it closing underneath
export const CODE_LENS_HOVER_GRACE_MS = 200;

const setCodeLenses = StateEffect.define<CodeLensSpec[]>();
const setHoveredLens = StateEffect.define<CodeLensSpec | null>();

function specEquals(a: CodeLensSpec, b: CodeLensSpec): boolean {
  return (
    a.pos === b.pos &&
    a.kind === b.kind &&
    a.name === b.name &&
    a.cache?.boundName === b.cache?.boundName &&
    a.cache?.cacheName === b.cache?.cacheName
  );
}

/**
 * Per-view hover state shared by the lens icons and their popover, so the
 * popover stays open while the pointer is over either of them.
 */
class LensHoverController {
  private readonly view: EditorView;
  private showTimer: number | undefined;
  private hideTimer: number | undefined;

  constructor(view: EditorView) {
    this.view = view;
  }

  /** Pointer entered a lens icon */
  enterLens(spec: CodeLensSpec, icon: HTMLElement): void {
    this.clearTimers();
    dismissEditorHoverTooltips(this.view, icon);
    const hovered = this.view.state.field(codeLensHoverField, false);
    if (hovered && specEquals(hovered.spec, spec)) {
      // Already showing this lens (e.g. pointer came back from the popover)
      return;
    }
    this.showTimer = window.setTimeout(() => {
      this.showTimer = undefined;
      this.view.dispatch({ effects: setHoveredLens.of(spec) });
    }, CODE_LENS_HOVER_DELAY_MS);
  }

  /** Pointer left a lens icon or the popover */
  leave(): void {
    this.clearTimers();
    this.hideTimer = window.setTimeout(() => {
      this.hideTimer = undefined;
      this.hide();
    }, CODE_LENS_HOVER_GRACE_MS);
  }

  /** Pointer entered the popover */
  enterPopover(): void {
    window.clearTimeout(this.hideTimer);
    this.hideTimer = undefined;
  }

  hide(): void {
    this.clearTimers();
    if (this.view.state.field(codeLensHoverField, false)) {
      this.view.dispatch({ effects: setHoveredLens.of(null) });
    }
  }

  destroy(): void {
    this.clearTimers();
  }

  private clearTimers(): void {
    window.clearTimeout(this.showTimer);
    window.clearTimeout(this.hideTimer);
    this.showTimer = undefined;
    this.hideTimer = undefined;
  }
}

const lensHoverPlugin = ViewPlugin.define(
  (view) => new LensHoverController(view),
);

/**
 * Keeps the editor's own hover tooltips (LSP / documentation hints) from
 * showing for the token the icon sits after.
 *
 * CodeMirror's `hoverTooltip` tracks the last `mousemove` seen on `view.dom`
 * and, once the pointer has rested for its hover delay, opens a tooltip for
 * that position. The icon swallows `mousemove` (see the widget), so a pointer
 * resting on the icon looks to CodeMirror like a pointer resting on the last
 * character it crossed on the way in, and any hover already open for that
 * token never gets closed. A `mouseleave` on `view.dom` is the signal it uses
 * to cancel a pending hover and close an open one, so synthesize that.
 */
function dismissEditorHoverTooltips(
  view: EditorView,
  relatedTarget: HTMLElement,
): void {
  view.dom.dispatchEvent(new MouseEvent("mouseleave", { relatedTarget }));
}

class CodeLensWidget extends WidgetType {
  private readonly spec: CodeLensSpec;

  constructor(spec: CodeLensSpec) {
    super();
    this.spec = spec;
  }

  override eq(other: CodeLensWidget): boolean {
    // `pos` is captured by the DOM hover/click handlers, so a reused widget
    // whose anchor moved must not be treated as equal
    return specEquals(this.spec, other.spec);
  }

  override toDOM(view: EditorView): HTMLElement {
    const { spec } = this;
    const element = document.createElement("span");
    element.className = "mo-code-lens";
    element.setAttribute("role", "button");
    // Focusable so the action is reachable and activatable by keyboard
    element.tabIndex = 0;
    // No `title`: the native tooltip is replaced by the hover popover
    element.setAttribute("aria-label", LENS_TOOLTIPS[spec.kind]);
    // Static, trusted markup (see icons.ts)
    element.innerHTML = LENS_ICONS[spec.kind];
    const hover = () => view.plugin(lensHoverPlugin);
    const hidePopover = () => hover()?.hide();
    element.onmouseenter = () => hover()?.enterLens(spec, element);
    element.onmouseleave = () => hover()?.leave();
    element.onmousemove = (event) => {
      // Keep the editor's built-in hover tooltip from re-arming while the
      // pointer is over the icon (see `dismissEditorHoverTooltips`)
      event.stopPropagation();
    };
    element.onmousedown = (event) => {
      // Don't move the cursor or steal focus from the editor
      event.preventDefault();
      event.stopPropagation();
    };
    element.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      hidePopover();
      openLensTarget(spec.kind);
    };
    element.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        event.stopPropagation();
        hidePopover();
        openLensTarget(spec.kind);
      }
    };
    return element;
  }

  override ignoreEvent(): boolean {
    // The widget handles its own events
    return true;
  }
}

interface HoveredLens {
  spec: CodeLensSpec;
  tooltip: Tooltip;
}

function createHoveredLens(spec: CodeLensSpec): HoveredLens {
  const tooltip: Tooltip = {
    pos: spec.pos,
    above: true,
    create: (view) => {
      const dom = document.createElement("div");
      // Same chrome as the SQL completion/hover popovers
      dom.classList.add("mo-cm-tooltip", "docs-documentation");
      // The popover is scrollable, so keep it open while the pointer is
      // inside it
      dom.onmouseenter = () => view.plugin(lensHoverPlugin)?.enterPopover();
      dom.onmouseleave = () => view.plugin(lensHoverPlugin)?.leave();
      const unmount = mountLensPopover(dom, spec);
      return { dom, resize: false, destroy: unmount };
    },
  };
  return { spec, tooltip };
}

const codeLensHoverField = StateField.define<HoveredLens | null>({
  create() {
    return null;
  },
  update(hovered, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setHoveredLens)) {
        return effect.value ? createHoveredLens(effect.value) : null;
      }
      if (effect.is(setCodeLenses) && hovered) {
        // Lenses were rebuilt (e.g. after a store update); keep the popover
        // only if the hovered lens is still there, unchanged
        const stillPresent = effect.value.some((spec) =>
          specEquals(spec, hovered.spec),
        );
        return stillPresent ? hovered : null;
      }
    }
    return tr.docChanged ? null : hovered;
  },
  provide: (field) =>
    showTooltip.from(field, (hovered) => hovered?.tooltip ?? null),
});

const codeLensField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none;
  },
  update(decorations, tr) {
    decorations = decorations.map(tr.changes);
    for (const effect of tr.effects) {
      if (effect.is(setCodeLenses)) {
        decorations = Decoration.set(
          effect.value.map((spec) =>
            Decoration.widget({
              widget: new CodeLensWidget(spec),
              side: 1,
            }).range(spec.pos),
          ),
          // Variable and cache lenses are collected separately, so sort
          true,
        );
      }
    }
    return decorations;
  },
  provide: (field) => EditorView.decorations.from(field),
});

/**
 * Plugin that keeps code lens decorations in sync with the document and the
 * datasource/bucket state.
 */
class CodeLensPlugin {
  private readonly view: EditorView;
  private readonly cellId: CellId;
  private readonly includeCache: boolean;
  private readonly unsubscribes: Array<() => void>;

  // Delay (in ms) before recomputing lenses after user changes or store updates
  private readonly debounceMs = 300;
  private readonly scheduleUpdate: DebouncedFunc<() => void>;

  constructor(view: EditorView, cellId: CellId, includeCache: boolean) {
    this.view = view;
    this.cellId = cellId;
    this.includeCache = includeCache;
    this.scheduleUpdate = debounce(() => this.run(), this.debounceMs);
    const onStoreChange = () => this.scheduleUpdate();
    this.unsubscribes = [
      store.sub(datasetTablesAtom, onStoreChange),
      store.sub(dataConnectionsMapAtom, onStoreChange),
      store.sub(storageNamespacesAtom, onStoreChange),
      // The declaring-cell filter depends on variables
      store.sub(variablesAtom, onStoreChange),
    ];
    this.scheduleUpdate();
  }

  update(update: ViewUpdate) {
    // Recompute on edits, and when the cell's language changes (e.g. Python ->
    // SQL) so stale Python-only icons are cleared even if the text is unchanged
    const adapterChanged =
      update.startState.field(languageAdapterState, false)?.type !==
      update.state.field(languageAdapterState, false)?.type;
    if (update.docChanged || adapterChanged) {
      this.scheduleUpdate();
    }
  }

  destroy() {
    this.scheduleUpdate.cancel();
    for (const unsubscribe of this.unsubscribes) {
      unsubscribe();
    }
  }

  private run() {
    const { state } = this.view;
    const lenses: CodeLensSpec[] = [];

    // Only python cells: SQL/markdown docs aren't python, and a cache icon
    // inside a SQL string would be misleading.
    const adapterType = state.field(languageAdapterState, false)?.type;
    if (adapterType == null || adapterType === "python") {
      const entities = getLensEntities(this.cellId);
      const targets = findDeclarationSites({
        state,
        names: new Set(entities.keys()),
      });
      for (const target of targets) {
        const kind = entities.get(target.name);
        if (kind) {
          lenses.push({ pos: target.to, kind, name: target.name });
        }
      }
      if (this.includeCache) {
        for (const site of findCacheSites(state)) {
          lenses.push({
            pos: site.to,
            kind: "cache",
            name: `cache:${site.from}`,
            cache: { boundName: site.boundName, cacheName: site.cacheName },
          });
        }
      }
    }

    // Defer dispatch to avoid triggering during an editor update cycle
    queueMicrotask(() => {
      this.view.dispatch({ effects: setCodeLenses.of(lenses) });
    });
  }
}

// Padding around the 12px icon so the hover/click target isn't tiny
const LENS_HIT_PADDING = "3px";

const codeLensTheme = EditorView.baseTheme({
  ".mo-code-lens": {
    display: "inline-flex",
    verticalAlign: "baseline",
    // Optically center the icon against the text
    transform: "translateY(1.5px)",
    // Enlarge the hit area without affecting layout: the padding is pulled
    // back in with negative vertical margins so the line height is unchanged
    padding: LENS_HIT_PADDING,
    margin: `-${LENS_HIT_PADDING} 0 -${LENS_HIT_PADDING} calc(0.3em - ${LENS_HIT_PADDING})`,
    cursor: "pointer",
    opacity: "0.5",
  },
  ".mo-code-lens:hover": {
    opacity: "1",
  },
});

/**
 * Inline icons linking datasource/bucket variables and `mo.cache` /
 * `mo.persistent_cache` calls to their panels.
 * Configurable via the `display.code_lens` user config (on by default).
 */
export function codeLensBundle(cellId: CellId, enabled = true): Extension {
  if (!enabled) {
    return [];
  }
  return [
    codeLensField,
    codeLensHoverField,
    lensHoverPlugin,
    ViewPlugin.define(
      (view) => new CodeLensPlugin(view, cellId, getFeatureFlag("cache_panel")),
    ),
    codeLensTheme,
  ];
}
