/* Copyright 2026 Marimo. All rights reserved. */

import { diff } from "@codemirror/merge";
import {
  type EditorState,
  type StateEffect,
  Transaction,
  type TransactionSpec,
} from "@codemirror/state";
import { suppressSignatureHelp } from "@marimo-team/codemirror-languageserver";
import { dequal } from "dequal";
import {
  languageAdapterFromCode,
  languageAdapterState,
  languageConfigurationEffects,
} from "./extension";
import { LanguageAdapters } from "./LanguageAdapters";
import { sqlDialectEffect } from "./languages/sql/sql";
import { languageMetadataField, setLanguageMetadata } from "./metadata";

/** The Python source represented by the editor's text and language metadata. */
export function getCellCode(state: EditorState): string {
  const text = state.doc.toString();
  const adapter = state.field(languageAdapterState, false);
  return adapter
    ? adapter.transformOut(
        text,
        state.field(languageMetadataField, false) ?? {},
      )[0]
    : text;
}

/** Account for adapters normalizing quotes and whitespace when reading source. */
export function editorShowsCellCode(
  state: EditorState,
  source: string,
): boolean {
  if (getCellCode(state) === source) {
    return true;
  }
  const adapter = state.field(languageAdapterState, false);
  if (!adapter?.isSupported(source)) {
    return false;
  }
  const [text, , metadata] = adapter.transformIn(source);
  return (
    text === state.doc.toString() &&
    dequal(metadata, state.field(languageMetadataField, false))
  );
}

/**
 * Prepare one update to the editor's text, language, and metadata.
 * Existing editors keep a compatible mode; only initial loading infers one.
 * The caller decides whether this is a local edit or a remote synchronization.
 */
export function prepareCellCodeUpdate(
  state: EditorState,
  source: string,
  { initialize = false }: { initialize?: boolean } = {},
): TransactionSpec | null {
  const current = state.field(languageAdapterState, false);
  let target = current;
  if (current) {
    if (initialize) {
      target = languageAdapterFromCode(source);
    } else if (!current.isSupported(source)) {
      target = LanguageAdapters.python;
    }
  }
  const languageChanged = target?.type !== current?.type;
  if (!languageChanged && editorShowsCellCode(state, source)) {
    return null;
  }

  const effects: StateEffect<unknown>[] = [];
  let text = source;
  if (target) {
    if (languageChanged) {
      effects.push(...languageConfigurationEffects(state, target));
    }
    const [inner, , metadata] = target.transformIn(source);
    text = inner;
    const metadataChanged = !dequal(
      metadata,
      state.field(languageMetadataField, false),
    );
    if (metadataChanged) {
      effects.push(setLanguageMetadata.of(metadata));
    }
    if (target.type === "sql" && (languageChanged || metadataChanged)) {
      effects.push(sqlDialectEffect(metadata.engine));
    }
  }

  // Match the merge view's scan limit so large rewrites stay bounded. The diff
  // maps selections, folds, and diagnostics through each individual edit.
  const changes = diff(state.doc.toString(), text, { scanLimit: 500 }).map(
    (change) => ({
      from: change.fromA,
      to: change.toA,
      insert: text.slice(change.fromB, change.toB),
    }),
  );
  return {
    changes,
    effects,
    annotations: [
      suppressSignatureHelp.of(true),
      // History was reset with the language; the previous text uses another representation.
      ...(languageChanged ? [Transaction.addToHistory.of(false)] : []),
    ],
  };
}
