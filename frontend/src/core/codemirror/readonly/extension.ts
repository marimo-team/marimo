/* Copyright 2024 Marimo. All rights reserved. */
import { Compartment, EditorState, StateEffect } from "@codemirror/state";
import { type EditorView, ViewPlugin } from "@codemirror/view";
import { WebSocketState } from "../../websocket/types";
import { connectionAtom } from "../../network/connection";
import type { createStore } from "jotai";

/**
 * State effect for updating readonly status based on connection
 */
const updateReadonlyEffect = StateEffect.define<boolean>();

/**
 * Compartment for managing readonly configuration
 */
const readonlyCompartment = new Compartment();

// Floating indicator plugin
const INDICATOR_ID = "marimo-connecting-indicator";
function getOrCreateIndicator(): HTMLDivElement {
  let indicator = document.getElementById(
    INDICATOR_ID,
  ) as HTMLDivElement | null;
  if (!indicator) {
    indicator = document.createElement("div");
    indicator.id = INDICATOR_ID;
    indicator.textContent = "Connecting…";
    indicator.style.position = "fixed";
    indicator.style.zIndex = "9999";
    indicator.style.background = "#222";
    indicator.style.color = "#fff";
    indicator.style.padding = "2px 8px";
    indicator.style.borderRadius = "6px";
    indicator.style.fontSize = "0.9em";
    indicator.style.boxShadow = "0 2px 8px rgba(0,0,0,0.15)";
    indicator.style.pointerEvents = "none";
    indicator.style.display = "none";
    document.body.append(indicator);
  }
  return indicator;
}

function showIndicatorAt(left: number, top: number) {
  const indicator = getOrCreateIndicator();
  indicator.style.left = `${left}px`;
  indicator.style.top = `${top}px`;
  indicator.style.display = "block";
  indicator.textContent = "Connecting…";
}
function hideIndicator() {
  const indicator = document.getElementById(INDICATOR_ID);
  if (indicator) {
    indicator.style.display = "none";
  }
}

let hideIndicatorTimeout: number | null = null;

/**
 * Creates a dynamic readonly extension that toggles based on WebSocket connection status.
 * When disconnected or connecting, the editor becomes readonly.
 * When connected, the editor becomes editable.
 */
export function createDynamicReadonlyExtension(
  store: ReturnType<typeof createStore>,
) {
  // Initial readonly state - start as readonly until connected
  let isReadonly = true;

  const connectingIndicatorPlugin = ViewPlugin.define((view) => {
    let listenersAttached = false;
    const dom = view.dom;

    function showNearCaret() {
      const sel = view.state.selection.main;
      const coords = view.coordsAtPos(sel.head);
      if (coords) {
        showIndicatorAt(coords.left + 2, coords.bottom + 2);
      } else {
        showIndicatorAt(window.innerWidth / 2, window.innerHeight * 0.1);
      }
      if (hideIndicatorTimeout) {
        window.clearTimeout(hideIndicatorTimeout);
      }
      hideIndicatorTimeout = window.setTimeout(hideIndicator, 1500);
    }

    function onUserInput() {
      showNearCaret();
    }

    function attachListeners() {
      if (!listenersAttached) {
        dom.addEventListener("keydown", onUserInput, true);
        dom.addEventListener("paste", onUserInput, true);
        listenersAttached = true;
      }
    }
    function detachListeners() {
      if (listenersAttached) {
        dom.removeEventListener("keydown", onUserInput, true);
        dom.removeEventListener("paste", onUserInput, true);
        listenersAttached = false;
      }
    }

    // Subscribe to connectionAtom and manage listeners
    const unsubscribe = store.sub(connectionAtom, () => {
      const connection = store.get(connectionAtom);
      if (connection.state === WebSocketState.CONNECTING) {
        attachListeners();
      } else {
        detachListeners();
        hideIndicator();
      }
    });

    // On init, check if we should attach
    if (store.get(connectionAtom).state === WebSocketState.CONNECTING) {
      attachListeners();
    }

    return {
      destroy() {
        detachListeners();
        unsubscribe();
        hideIndicator();
      },
    };
  });

  return [
    // Initial readonly configuration
    readonlyCompartment.of(EditorState.readOnly.of(isReadonly)),

    // Transaction extender to handle readonly updates
    EditorState.transactionExtender.of((tr) => {
      for (const effect of tr.effects) {
        if (effect.is(updateReadonlyEffect)) {
          const newReadonly = effect.value;
          if (newReadonly !== isReadonly) {
            isReadonly = newReadonly;
            return {
              effects: readonlyCompartment.reconfigure(
                EditorState.readOnly.of(newReadonly),
              ),
            };
          }
        }
      }
      return null;
    }),

    // View plugin to manage connection subscription
    ViewPlugin.define((view) => {
      const unsubscribe = store.sub(connectionAtom, () => {
        const connection = store.get(connectionAtom);
        const shouldBeReadonly = connection.state !== WebSocketState.OPEN;

        // Dispatch effect to update readonly state
        view.dispatch({
          effects: updateReadonlyEffect.of(shouldBeReadonly),
        });
      });

      return {
        destroy() {
          unsubscribe();
        },
      };
    }),

    // Floating indicator plugin
    connectingIndicatorPlugin,
  ];
}

/**
 * Manually update readonly state for a specific view
 */
export function updateReadonlyState(view: EditorView, readonly: boolean) {
  view.dispatch({
    effects: updateReadonlyEffect.of(readonly),
  });
}

/**
 * Check if the editor is currently readonly
 */
export function isEditorReadonly(state: EditorState): boolean {
  return state.facet(EditorState.readOnly);
}
