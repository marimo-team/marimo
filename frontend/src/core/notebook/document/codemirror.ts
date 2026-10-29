/* Copyright 2026 Marimo. All rights reserved. */

/**
 * A CodeMirror binding between an editor and one cell's code.
 *
 * The editor and the document model each hold the code, and the binding keeps
 * them equal in both directions.
 *
 * - Push. An update that could change the code writes it to the model before
 *   the update returns, so the model keeps pace with typing.
 * - Pull. A model change reaches the editor in a microtask, because a view
 *   cannot dispatch while it is constructing or updating. The binding keeps
 *   the code both sides last agreed on, so the model's echo of a push is
 *   skipped while a different value, even one written during that push, is
 *   pulled. A real change is marked remote, stays out of undo history, and
 *   waits for IME composition to end.
 *
 * The editor shows code through marimo's language adapters, so a markdown
 * cell edits the text inside `mo.md`. Both directions compare the cell's
 * Python code rather than the editor text, so an adapter that normalizes what
 * it reads back leaves typing alone.
 *
 * A pulled change replaces only what differs, using `diff` from
 * `@codemirror/merge`. Separate edits stay separate, so the selection, folds,
 * and diagnostics between them keep their place. The diff uses a scan limit of
 * 500, as the merge view does. Past it, the search trades precision for speed,
 * so a rewrite of a large cell costs microseconds and maps the selection
 * coarsely instead of blocking the editor.
 */

import { diff } from "@codemirror/merge";
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
import type { Atom, createStore } from "jotai/vanilla";
import {
  languageAdapterFromCode,
  languageAdapterState,
  switchLanguage,
} from "../../codemirror/language/extension";
import { initializeSQLDialect } from "../../codemirror/language/languages/sql/sql";
import {
  languageMetadataField,
  setLanguageMetadata,
} from "../../codemirror/language/metadata";
import type { DocumentModel } from "./model";
import { selectCellField } from "./select";

/** The diff scan limit, matching the default of the merge view. */
const SCAN_LIMIT = 500;

interface Binding {
  readonly store: ReturnType<typeof createStore>;
  readonly model: DocumentModel;
  readonly cellId: CellId;
  /** Undefined while the cell is absent, null while its source is withheld. */
  readonly code: Atom<string | null | undefined>;
}

/**
 * Bind an editor to one cell's code.
 *
 * Editors without marimo's language configuration bind their text as is.
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
  const binding: Binding = {
    store,
    model,
    cellId,
    code: selectCellField(model.documentAtom, cellId, "code"),
  };
  return ViewPlugin.define((view) => new CellCodeSync(view, binding), {
    eventObservers: {
      compositionend() {
        this.compositionEnded();
      },
    },
  });
}

class CellCodeSync {
  #scheduled = false;
  /** A pull arrived during IME composition and runs once it ends. */
  #deferred = false;
  /**
   * A pull is dispatching to the editor.
   *
   * A language switch dispatches transactions of its own before the text, and
   * their in-between states represent the wrong code. Until the switch can be
   * part of the pull's one remote transaction, this keeps them from pushing.
   */
  #pulling = false;
  /**
   * The code the editor and the model last agreed on.
   *
   * A change the model cannot take clears it, so once the cell is available
   * again its code is pulled even if it matches what was agreed before.
   */
  #synced: string | undefined;
  #destroyed = false;
  readonly #view: EditorView;
  readonly #binding: Binding;
  readonly #unsubscribe: () => void;

  public constructor(view: EditorView, binding: Binding) {
    this.#view = view;
    this.#binding = binding;
    // A change to the agreed code is the echo of a push and needs no pull.
    this.#unsubscribe = binding.store.sub(binding.code, () => {
      if (binding.store.get(binding.code) !== this.#synced) {
        this.#schedule();
      }
    });
    this.#schedule();
  }

  public update(update: ViewUpdate) {
    if (!this.#pulling && changesCode(update)) {
      this.#push(update.state);
    }
    if (this.#deferred && !update.view.composing) {
      this.#schedule();
    }
  }

  /**
   * Run a pull that waited for the composition.
   *
   * A composition that ends without changing the text need not produce an
   * update. CodeMirror finishes handling the end in a microtask, so the pull
   * waits for the next task.
   */
  public compositionEnded() {
    if (this.#deferred) {
      setTimeout(() => this.#schedule(), 0);
    }
  }

  public destroy() {
    this.#destroyed = true;
    this.#unsubscribe();
  }

  /** Write the editor's code to the model unless the editor already shows it. */
  #push(state: EditorState) {
    const { store, model, cellId, code } = this.#binding;
    const current = store.get(code);
    if (typeof current !== "string") {
      this.#synced = undefined;
      return;
    }
    if (shows(state, current)) {
      this.#synced = current;
      return;
    }
    const next = codeOf(state);
    this.#synced = next;
    store.set(model.editAtom, (tx) => tx.setCode(cellId, next));
  }

  /** Show the model's code unless the editor already shows it. */
  #pull() {
    this.#scheduled = false;
    const next = this.#binding.store.get(this.#binding.code);
    if (this.#destroyed || typeof next !== "string") {
      return;
    }
    if (this.#view.composing) {
      this.#deferred = true;
      return;
    }
    this.#deferred = false;
    if (next !== this.#synced && !shows(this.#view.state, next)) {
      this.#pulling = true;
      try {
        replaceCode(this.#view, next);
      } finally {
        this.#pulling = false;
      }
    }
    this.#synced = next;
  }

  /** Pull once after the current update, however many changes arrive. */
  #schedule() {
    if (!this.#scheduled) {
      this.#scheduled = true;
      queueMicrotask(() => this.#pull());
    }
  }
}

/**
 * The cell code an editor state represents.
 *
 * With a language adapter, this is the adapter's Python for the editor text.
 */
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

/**
 * Whether an editor state shows the given cell code.
 *
 * An adapter can spell the same code more than one way, such as `mo.md("hi")`
 * and its canonical form, so a state shows code that reads into its text and
 * metadata as well as the code its own spelling produces.
 */
function shows(state: EditorState, code: string): boolean {
  if (codeOf(state) === code) {
    return true;
  }
  const adapter = state.field(languageAdapterState, false);
  if (!adapter) {
    return false;
  }
  const [text, , metadata] = adapter.transformIn(code);
  return (
    text === state.doc.toString() &&
    dequal(metadata, state.field(languageMetadataField, false))
  );
}

/**
 * Whether an update could change the code an editor represents.
 *
 * Language metadata, such as an SQL cell's output name, changes the code
 * without changing the text.
 */
function changesCode(update: ViewUpdate): boolean {
  return (
    update.docChanged ||
    update.state.field(languageAdapterState, false) !==
      update.startState.field(languageAdapterState, false) ||
    update.state.field(languageMetadataField, false) !==
      update.startState.field(languageMetadataField, false)
  );
}

/**
 * Show cell code in the language it implies.
 *
 * The language switch happens first, in its own transactions, and clears undo
 * history because its entries edit the previous language's text. The text and
 * metadata follow in one remote transaction that undo history leaves out. An
 * SQL dialect depends on the engine in the metadata, so it is set again after.
 */
function replaceCode(view: EditorView, code: string) {
  let text = code;
  const effects: StateEffect<unknown>[] = [];
  let sql = false;
  const adapter = view.state.field(languageAdapterState, false);
  if (adapter) {
    const target = languageAdapterFromCode(code);
    sql = target.type === "sql";
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
    changes: changesBetween(current, text),
    effects,
    annotations: [
      Transaction.remote.of(true),
      Transaction.addToHistory.of(false),
    ],
  });
  if (sql && effects.length > 0) {
    initializeSQLDialect(view);
  }
}

/** The changes that turn one text into another, one per edited range. */
function changesBetween(from: string, to: string): ChangeSpec {
  return diff(from, to, { scanLimit: SCAN_LIMIT }).map((change) => ({
    from: change.fromA,
    to: change.toA,
    insert: to.slice(change.fromB, change.toB),
  }));
}
