/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Remember which headers this browser folded, per notebook, across reloads.
 *
 * Cell ids are new on every load, so a folded header is remembered by its
 * heading instead: its level and text, and how many headers with the same
 * level and text come before it. Renaming or deleting other headers leaves
 * the key alone; renaming the folded header itself forgets the fold.
 */

import type { createStore } from "jotai";
import { z } from "zod";
import { NotebookScopedLocalStorage } from "@/utils/storage/typed";
import { canCollapseOutline } from "../dom/outline";
import { cellOutlinesAtom, notebookAtom } from "./cells";
import type { CellId } from "./ids";
import { collapsedAtom } from "./layout";
import type { Outline } from "./outline";

const BASE_KEY = "marimo:collapsed-headings";

export interface CollapsedHeadingsStorage {
  get(key: string): string[];
  set(key: string, value: string[]): void;
}

let defaultStorage: CollapsedHeadingsStorage | undefined;

function getDefaultStorage(): CollapsedHeadingsStorage {
  defaultStorage ??= new NotebookScopedLocalStorage<string[]>(
    BASE_KEY,
    z.array(z.string()),
    () => [],
  );
  return defaultStorage;
}

/** The key each header cell is remembered by, in notebook order. */
export function headingKeys(
  ids: readonly CellId[],
  outlineOf: (id: CellId) => Outline | null | undefined,
): Map<CellId, string> {
  const keys = new Map<CellId, string>();
  const seen = new Map<string, number>();
  for (const id of ids) {
    const outline = outlineOf(id) ?? null;
    if (!canCollapseOutline(outline)) {
      continue;
    }
    const first = outline?.items[0];
    if (first === undefined) {
      continue;
    }
    const heading = `${first.level}:${first.name}`;
    const occurrence = seen.get(heading) ?? 0;
    seen.set(heading, occurrence + 1);
    keys.set(id, `${heading}#${occurrence}`);
  }
  return keys;
}

/**
 * Fold the headers this notebook had folded when it was last open, as their
 * outlines arrive, and save the folds on each change, until the signal aborts.
 *
 * A saved fold is applied once, the first time its header appears, so that
 * unfolding it afterwards sticks. Saved folds whose header has not appeared
 * yet are kept, since outlines arrive as cells run.
 */
export function followCollapsedHeadings({
  store,
  signal,
  storage = getDefaultStorage(),
}: {
  store: ReturnType<typeof createStore>;
  signal: AbortSignal;
  storage?: CollapsedHeadingsStorage;
}): void {
  const pending = new Set(storage.get(BASE_KEY));

  const currentKeys = () => {
    const outlines = store.get(cellOutlinesAtom);
    return headingKeys(store.get(notebookAtom).cellIds, (id) => outlines[id]);
  };

  const save = (keys: Map<CellId, string>) => {
    const collapsed = store.get(collapsedAtom);
    const saved = new Set(pending);
    for (const [id, key] of keys) {
      if (collapsed.has(id)) {
        saved.add(key);
      }
    }
    storage.set(BASE_KEY, [...saved]);
  };

  const restore = () => {
    const keys = currentKeys();
    const toFold: CellId[] = [];
    for (const [id, key] of keys) {
      if (pending.delete(key)) {
        toFold.push(id);
      }
    }
    if (toFold.length > 0) {
      // Saves through the collapsedAtom subscription.
      store.set(
        collapsedAtom,
        (collapsed) => new Set([...collapsed, ...toFold]),
      );
    } else {
      save(keys);
    }
  };

  const unsubscribeOutlines = store.sub(cellOutlinesAtom, restore);
  const unsubscribeCollapsed = store.sub(collapsedAtom, () =>
    save(currentKeys()),
  );
  signal.addEventListener(
    "abort",
    () => {
      unsubscribeOutlines();
      unsubscribeCollapsed();
    },
    { once: true },
  );
  restore();
}
