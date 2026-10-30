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

import {
  type EditorState,
  type Extension,
  Transaction,
} from "@codemirror/state";
import { type EditorView, ViewPlugin, type ViewUpdate } from "@codemirror/view";
import type { CellId } from "@marimo-team/client/protocol";
import type { Atom, createStore } from "jotai/vanilla";
import {
  editorShowsCellCode,
  getCellCode,
  prepareCellCodeUpdate,
} from "../../codemirror/language/cell-code";
import { languageAdapterState } from "../../codemirror/language/extension";
import { languageMetadataField } from "../../codemirror/language/metadata";
import type { DocumentModel } from "./model";
import { selectCellField } from "./select";

interface Binding {
  readonly store: ReturnType<typeof createStore>;
  readonly model: DocumentModel;
  readonly cellId: CellId;
  /** Undefined while the cell is absent, null while its source is withheld. */
  readonly code: Atom<string | null | undefined>;
  /** Whether the editor shows the model's code, or only writes its own. */
  readonly follow: boolean;
}

/**
 * Bind an editor to one cell's code.
 *
 * Editors without marimo's language configuration bind their text as is.
 * With `follow` off the editor only pushes, for an editor whose text has
 * another source of remote changes.
 */
export function cellCodeBinding({
  store,
  model,
  cellId,
  follow = true,
}: {
  store: ReturnType<typeof createStore>;
  model: DocumentModel;
  cellId: CellId;
  follow?: boolean;
}): Extension {
  const binding: Binding = {
    store,
    model,
    cellId,
    code: selectCellField(model.documentAtom, cellId, "code"),
    follow,
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
  // Only the initial load infers a mode; subsequent edits preserve it.
  #initialized = false;
  #scheduled = false;
  /** A pull arrived during IME composition and runs once it ends. */
  #deferred = false;
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
    if (!binding.follow) {
      this.#initialized = true;
      this.#unsubscribe = () => undefined;
      return;
    }
    // A change to the agreed code is the echo of a push and needs no pull.
    this.#unsubscribe = binding.store.sub(binding.code, () => {
      if (binding.store.get(binding.code) !== this.#synced) {
        this.#schedule();
      }
    });
    this.#schedule();
  }

  public update(update: ViewUpdate) {
    if (
      changesCode(update) &&
      !update.transactions.every((tr) => tr.annotation(Transaction.remote))
    ) {
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
    this.#initialized = true;
    const { store, model, cellId, code } = this.#binding;
    const current = store.get(code);
    if (typeof current !== "string") {
      this.#synced = undefined;
      return;
    }
    if (editorShowsCellCode(state, current)) {
      this.#synced = current;
      return;
    }
    const next = getCellCode(state);
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
    if (next !== this.#synced) {
      const update = prepareCellCodeUpdate(this.#view.state, next, {
        initialize: !this.#initialized,
      });
      if (update) {
        this.#view.dispatch(update, {
          annotations: [
            Transaction.remote.of(true),
            Transaction.addToHistory.of(false),
          ],
        });
      }
    }
    this.#synced = next;
    this.#initialized = true;
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
