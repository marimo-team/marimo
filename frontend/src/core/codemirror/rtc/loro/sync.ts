/* Copyright 2024 Marimo. All rights reserved. */

// Vendored from https://github.com/loro-dev/loro-codemirror/blob/main/src/index.ts
// and adapted to support:
// - custom `getTextFromDoc`
// - filter diffs by path

import type { Extension } from "@codemirror/state";
import { Annotation, type ChangeSpec } from "@codemirror/state";
import type { EditorView, PluginValue, ViewUpdate } from "@codemirror/view";
import { ViewPlugin } from "@codemirror/view";
import type {
  LoroDoc,
  LoroEventBatch,
  LoroText,
  Subscription,
} from "loro-crdt";

/**
 * It is used to sync the document with the remote users.
 *
 * @param doc - LoroDoc instance
 * @returns Extension
 */
export const loroSyncPlugin = (
  doc: LoroDoc,
  docPath: string[],
  getTextFromDoc: (doc: LoroDoc) => LoroText,
): Extension => {
  return ViewPlugin.define(
    (view) => new LoroSyncPluginValue(view, doc, docPath, getTextFromDoc),
  );
};

/**
 * Annotation to identify loro sync changes (syncing from remote to local)
 */
export const loroSyncAnnotation = Annotation.define();

export class LoroSyncPluginValue implements PluginValue {
  sub?: Subscription;
  private isInitDispatch = false;

  constructor(
    private view: EditorView,
    private doc: LoroDoc,
    private docPath: string[],
    private getTextFromDoc: (doc: LoroDoc) => LoroText,
  ) {
    this.sub = doc.subscribe(this.onRemoteUpdate);
    Promise.resolve().then(() => {
      this.isInitDispatch = true;
      const currentText = this.view.state.doc.toString();
      const text = this.getTextFromDoc(this.doc);

      if (currentText === text.toString()) {
        return;
      }
      view.dispatch({
        changes: [
          {
            from: 0,
            to: this.view.state.doc.length,
            insert: text.toString(),
          },
        ],
      });
    });
  }

  onRemoteUpdate = (e: LoroEventBatch) => {
    if (e.by === "local") {
      return;
    }
    if (e.by === "checkout") {
      // TODO: better handle checkout
      this.view.dispatch({
        changes: [
          {
            from: 0,
            to: this.view.state.doc.length,
            insert: this.getTextFromDoc(this.doc).toString(),
          },
        ],
        annotations: [loroSyncAnnotation.of(this)],
      });
      return;
    }
    if (e.by === "import") {
      const changes: ChangeSpec[] = [];
      let pos = 0;
      for (const { diff, path } of e.events) {
        if (path.join("/") !== this.docPath.join("/")) {
          continue;
        }
        if (diff.type !== "text") {
          continue;
        }
        const textDiff = diff.diff;
        for (const delta of textDiff) {
          if (delta.insert) {
            changes.push({
              from: pos,
              to: pos,
              insert: delta.insert,
            });
          } else if (delta.delete) {
            changes.push({
              from: pos,
              to: pos + delta.delete,
            });
            pos += delta.delete;
          } else if (delta.retain != null) {
            pos += delta.retain;
          }
        }
        if (changes.length > 0) {
          this.view.dispatch({
            changes,
            annotations: [loroSyncAnnotation.of(this)],
          });
        }
      }
    }
  };

  update(update: ViewUpdate): void {
    if (this.isInitDispatch) {
      this.isInitDispatch = false;
      return;
    }

    if (
      !update.docChanged ||
      (update.transactions.length > 0 &&
        (update.transactions[0].annotation(loroSyncAnnotation) === this ||
          update.transactions[0].annotation(loroSyncAnnotation) === "undo"))
    ) {
      return;
    }
    let adj = 0;
    update.changes.iterChanges((fromA, toA, fromB, toB, insert) => {
      const insertText = insert.sliceString(0, insert.length, "\n");
      if (fromA !== toA) {
        this.getTextFromDoc(this.doc).delete(fromA + adj, toA - fromA);
      }
      if (insertText.length > 0) {
        this.getTextFromDoc(this.doc).insert(fromA + adj, insertText);
      }
      adj += insertText.length - (toA - fromA);
    });
    this.doc.commit();
  }

  destroy(): void {
    this.sub?.();
    this.sub = undefined;
  }
}
