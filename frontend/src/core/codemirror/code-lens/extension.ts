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

const setCodeLenses = StateEffect.define<CodeLensSpec[]>();
const setHoveredLens = StateEffect.define<CodeLensSpec | null>();

// Pending hover timers, keyed by widget element so `destroy` can cancel them
const HOVER_TIMERS = new WeakMap<HTMLElement, number>();

class CodeLensWidget extends WidgetType {
  private readonly spec: CodeLensSpec;

  constructor(spec: CodeLensSpec) {
    super();
    this.spec = spec;
  }

  override eq(other: CodeLensWidget): boolean {
    return (
      // `pos` is captured by the DOM hover/click handlers, so a reused widget
      // whose anchor moved must not be treated as equal
      this.spec.pos === other.spec.pos &&
      this.spec.kind === other.spec.kind &&
      this.spec.name === other.spec.name &&
      this.spec.cache?.boundName === other.spec.cache?.boundName &&
      this.spec.cache?.cacheName === other.spec.cache?.cacheName
    );
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
    const hidePopover = () => {
      window.clearTimeout(HOVER_TIMERS.get(element));
      HOVER_TIMERS.delete(element);
      if (view.state.field(codeLensHoverField, false)) {
        view.dispatch({ effects: setHoveredLens.of(null) });
      }
    };
    element.onmouseenter = () => {
      const timer = window.setTimeout(() => {
        view.dispatch({ effects: setHoveredLens.of(spec) });
      }, CODE_LENS_HOVER_DELAY_MS);
      HOVER_TIMERS.set(element, timer);
    };
    element.onmouseleave = hidePopover;
    element.onmousemove = (event) => {
      // Keep the editor's built-in hover documentation tooltip from also
      // triggering over the icon
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

  override destroy(dom: HTMLElement): void {
    window.clearTimeout(HOVER_TIMERS.get(dom));
    HOVER_TIMERS.delete(dom);
  }

  override ignoreEvent(): boolean {
    // The widget handles its own events
    return true;
  }
}

function createLensTooltip(spec: CodeLensSpec): Tooltip {
  return {
    pos: spec.pos,
    above: true,
    create: () => {
      const dom = document.createElement("div");
      // Same chrome as the SQL completion/hover popovers
      dom.classList.add("mo-cm-tooltip", "docs-documentation");
      const unmount = mountLensPopover(dom, spec);
      return { dom, resize: false, destroy: unmount };
    },
  };
}

const codeLensHoverField = StateField.define<Tooltip | null>({
  create() {
    return null;
  },
  update(tooltip, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setHoveredLens)) {
        return effect.value ? createLensTooltip(effect.value) : null;
      }
      if (effect.is(setCodeLenses)) {
        // Lenses were rebuilt; the hovered widget may be gone
        return null;
      }
    }
    return tr.docChanged ? null : tooltip;
  },
  provide: (field) => showTooltip.from(field),
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

const codeLensTheme = EditorView.baseTheme({
  ".mo-code-lens": {
    display: "inline-flex",
    verticalAlign: "baseline",
    // Optically center the icon against the text
    transform: "translateY(1.5px)",
    marginLeft: "0.3em",
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
 * Gated behind the `editor_code_lens` feature flag.
 */
export function codeLensBundle(cellId: CellId): Extension {
  if (!getFeatureFlag("editor_code_lens")) {
    return [];
  }
  return [
    codeLensField,
    codeLensHoverField,
    ViewPlugin.define(
      (view) => new CodeLensPlugin(view, cellId, getFeatureFlag("cache_panel")),
    ),
    codeLensTheme,
  ];
}
