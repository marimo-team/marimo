/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ChangeSpec,
  type EditorState,
  type Extension,
  type StateEffect,
  Transaction,
} from "@codemirror/state";
import { type EditorView, ViewPlugin, type ViewUpdate } from "@codemirror/view";
import type { CellId } from "@marimo-team/client/protocol";
import { dequal } from "dequal";
import type { createStore } from "jotai/vanilla";
import { selectAtom } from "jotai/vanilla/utils";
import {
  languageAdapterFromCode,
  languageAdapterState,
  switchLanguage,
} from "../codemirror/language/extension";
import {
  languageMetadataField,
  setLanguageMetadata,
} from "../codemirror/language/metadata";
import type { DocumentModel } from "./model";

/**
 * Bind an editor to one cell's code.
 *
 * The editor shows code through its language adapter, so a markdown cell
 * edits the text inside `mo.md`. Editors without marimo's language
 * configuration bind their text as is.
 *
 * Local changes write the draft synchronously, so the model agrees with the
 * editor after every update. Changes from elsewhere apply in a microtask,
 * switch to the language the code implies, replace only the text that
 * differs, stay out of undo history, and wait for IME composition to end.
 * The binding leaves an editor alone when it already shows the cell's code
 * in any language, and while the cell is absent or its source is withheld.
 */
export function cellCodeBinding({
  store,
  model,
  cellId,
}: {
  store: ReturnType<typeof createStore>;
  model: DocumentModel;
  cellId: CellId;
}): Extension {
  const codeAtom = selectAtom(model.cellAtom(cellId), (cell) => cell?.code);
  const code = () => store.get(codeAtom);

  return ViewPlugin.define((view) => {
    let destroyed = false;
    let scheduled = false;
    let deferred = false;
    // Switching language takes several transactions with code in between.
    let applying = false;

    function write(state: EditorState) {
      const current = code();
      const next = codeOf(state);
      if (typeof current === "string" && next !== current) {
        store.set(model.editAtom, (tx) => tx.setCode(cellId, next));
      }
    }

    function apply() {
      scheduled = false;
      const next = code();
      if (destroyed || typeof next !== "string") {
        return;
      }
      if (view.composing) {
        deferred = true;
        return;
      }
      deferred = false;
      // Includes the echo of local typing, which an adapter could normalize.
      if (codeOf(view.state) === next) {
        return;
      }
      applying = true;
      try {
        showCode(view, next);
      } finally {
        applying = false;
      }
    }

    // A view cannot dispatch while it is constructing or updating.
    function schedule() {
      if (!scheduled) {
        scheduled = true;
        queueMicrotask(apply);
      }
    }

    const unsubscribe = store.sub(codeAtom, schedule);
    schedule();
    return {
      update(update) {
        if (!applying && representationChanged(update)) {
          write(update.state);
        }
        if (deferred && !update.view.composing) {
          schedule();
        }
      },
      destroy() {
        destroyed = true;
        unsubscribe();
      },
    };
  });
}

/** The cell code an editor state represents. */
function codeOf(state: EditorState): string {
  const text = state.doc.toString();
  const adapter = state.field(languageAdapterState, false);
  return adapter
    ? adapter.transformOut(
        text,
        state.field(languageMetadataField, false) ?? {},
      )[0]
    : text;
}

function representationChanged(update: ViewUpdate): boolean {
  return (
    update.docChanged ||
    update.state.field(languageAdapterState, false) !==
      update.startState.field(languageAdapterState, false) ||
    update.state.field(languageMetadataField, false) !==
      update.startState.field(languageMetadataField, false)
  );
}

/** Show cell code in the language it implies, changing only what differs. */
function showCode(view: EditorView, code: string) {
  let text = code;
  const effects: StateEffect<unknown>[] = [];
  const adapter = view.state.field(languageAdapterState, false);
  if (adapter) {
    const target = languageAdapterFromCode(code);
    if (target.type !== adapter.type) {
      switchLanguage(view, { language: target.type, keepCodeAsIs: true });
    }
    const [inner, , metadata] = target.transformIn(code);
    text = inner;
    if (!dequal(metadata, view.state.field(languageMetadataField, false))) {
      effects.push(setLanguageMetadata.of(metadata));
    }
  }
  const current = view.state.doc.toString();
  if (current === text && effects.length === 0) {
    return;
  }
  view.dispatch({
    changes: difference(current, text),
    effects,
    annotations: [
      Transaction.remote.of(true),
      Transaction.addToHistory.of(false),
    ],
  });
}

/** One replacement from `from` to `to` that keeps their common prefix and suffix. */
function difference(from: string, to: string): ChangeSpec {
  const limit = Math.min(from.length, to.length);
  let start = 0;
  while (start < limit && from[start] === to[start]) {
    start++;
  }
  let end = 0;
  while (
    end < limit - start &&
    from[from.length - 1 - end] === to[to.length - 1 - end]
  ) {
    end++;
  }
  return {
    from: start,
    to: from.length - end,
    insert: to.slice(start, to.length - end),
  };
}
