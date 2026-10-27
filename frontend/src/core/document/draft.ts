/* Copyright 2026 Marimo. All rights reserved. */

import type { Document } from "../host";
import * as Protocol from "@marimo-team/client/protocol";

/** The fields a client edits. Null code means the host withheld source. */
export type EditableCell = Readonly<
  Pick<Protocol.Cell, "id" | "code" | "name">
> & {
  readonly config: Readonly<Protocol.CellConfig>;
};

type CellWithSource = EditableCell & { readonly code: string };

/** A confirmed document with a draft applied. */
export interface EditableDocument {
  readonly order: readonly Protocol.CellId[];
  readonly cells: ReadonlyMap<Protocol.CellId, EditableCell>;
}

/** Fields to change on a cell. A field left out keeps its value, including within config. */
export interface CellEdit {
  readonly code?: string;
  readonly name?: string;
  readonly config?: Partial<Readonly<Protocol.CellConfig>>;
}

type MutableEdit = { -readonly [K in keyof CellEdit]: CellEdit[K] };

/** Where a created cell goes. With neither, at the end. */
export interface Placement {
  readonly after?: Protocol.CellId;
  readonly before?: Protocol.CellId;
}

/** What this client wants one cell to become. */
type CellDraft =
  | { readonly kind: "edit"; readonly edit: CellEdit }
  | {
      readonly kind: "create";
      readonly cell: CellWithSource;
      readonly placement: Placement;
    }
  | { readonly kind: "delete" };

/**
 * This client's changes, layered over a confirmed document.
 *
 * A draft is a document delta in the terms of the host's edit request:
 * per-cell puts and deletes, and optionally the order as a whole. The view
 * a person edits and the request that synchronizes it both derive from it.
 */
export interface Draft {
  readonly cells: ReadonlyMap<Protocol.CellId, CellDraft>;
  /** The full order to apply, or null to follow the host's. */
  readonly order: readonly Protocol.CellId[] | null;
}

export const EMPTY_DRAFT: Draft = { cells: new Map(), order: null };

export function isEmptyDraft(draft: Draft): boolean {
  return draft.cells.size === 0 && draft.order === null;
}

// Merging -------------------------------------------------------------------

/** Copy the defined fields of `patch` over `base`. */
function assignDefined<T extends object>(base: T, patch: Partial<T>): T {
  const result = { ...base };
  for (const key in patch) {
    const value = patch[key];
    if (value !== undefined) {
      result[key] = value;
    }
  }
  return result;
}

/** The defined fields of `to` that differ from `from`. */
function differingFields<T extends object>(
  from: T,
  to: Partial<T>,
): Partial<T> {
  const result: Partial<T> = {};
  for (const key in to) {
    const value = to[key];
    if (value !== undefined && value !== from[key]) {
      result[key] = value;
    }
  }
  return result;
}

function isEmpty(object: object): boolean {
  return Object.keys(object).length === 0;
}

function sameOrder(
  a: readonly Protocol.CellId[],
  b: readonly Protocol.CellId[],
): boolean {
  return a.length === b.length && a.every((id, index) => id === b[index]);
}

/** Combine two edits, the later one winning field by field. */
function mergeEdit(previous: CellEdit, edit: CellEdit): CellEdit {
  const merged = assignDefined(previous, edit);
  return edit.config === undefined
    ? merged
    : { ...merged, config: assignDefined(previous.config ?? {}, edit.config) };
}

/** The cell with an edit applied, as a new object with the editable fields. */
function applyEdit(cell: CellWithSource, edit: CellEdit): CellWithSource;
function applyEdit(cell: EditableCell, edit: CellEdit): EditableCell;
function applyEdit(cell: EditableCell, edit: CellEdit): EditableCell {
  return {
    id: cell.id,
    code: edit.code ?? cell.code,
    name: edit.name ?? cell.name,
    config:
      edit.config === undefined
        ? cell.config
        : assignDefined(cell.config, edit.config),
  };
}

export function sameCell(a: EditableCell, b: EditableCell): boolean {
  return (
    a.id === b.id &&
    a.code === b.code &&
    a.name === b.name &&
    isEmpty(differingFields(a.config, b.config))
  );
}

/** The edit that turns `from` into `to`. Empty when they are the same. */
function editBetween(from: CellWithSource, to: CellWithSource): CellEdit {
  const edit: MutableEdit = {};
  if (to.code !== from.code) {
    edit.code = to.code;
  }
  if (to.name !== from.name) {
    edit.name = to.name;
  }
  const config = differingFields(from.config, to.config);
  if (!isEmpty(config)) {
    edit.config = config;
  }
  return edit;
}

/** The fields of `edit` still waiting after `sent` was accepted. */
function remainingEdit(edit: CellEdit, sent: CellEdit): CellEdit {
  const remaining: MutableEdit = {};
  if (edit.code !== undefined && edit.code !== sent.code) {
    remaining.code = edit.code;
  }
  if (edit.name !== undefined && edit.name !== sent.name) {
    remaining.name = edit.name;
  }
  if (edit.config !== undefined) {
    const config = differingFields(sent.config ?? {}, edit.config);
    if (!isEmpty(config)) {
      remaining.config = config;
    }
  }
  return remaining;
}

// Transitions ---------------------------------------------------------------
//
// Transitions are total. One with no effect returns its input, so a store
// can skip the write and its notifications.

function withCell(
  draft: Draft,
  id: Protocol.CellId,
  cell: CellDraft | undefined,
): Draft {
  const cells = new Map(draft.cells);
  if (cell === undefined) {
    cells.delete(id);
  } else {
    cells.set(id, cell);
  }
  return { ...draft, cells };
}

/** Place a cell, falling back to the end if its anchor has disappeared. */
function insertAt(
  order: readonly Protocol.CellId[],
  id: Protocol.CellId,
  placement: Placement,
): Protocol.CellId[] {
  const without = order.filter((other) => other !== id);
  let index = without.length;
  if (placement.after !== undefined) {
    const anchor = without.indexOf(placement.after);
    if (anchor !== -1) {
      index = anchor + 1;
    }
  } else if (placement.before !== undefined) {
    const anchor = without.indexOf(placement.before);
    if (anchor !== -1) {
      index = anchor;
    }
  }
  return [...without.slice(0, index), id, ...without.slice(index)];
}

/**
 * Edit a cell's fields.
 *
 * An edit to a cell the host has removed is dropped: there is no state to
 * apply it to. So is an edit to a cell this draft deletes.
 */
export function editCell(
  confirmed: Document,
  draft: Draft,
  id: Protocol.CellId,
  edit: CellEdit,
): Draft {
  const current = draft.cells.get(id);
  if (current?.kind === "delete") {
    return draft;
  }
  if (current?.kind === "create") {
    const cell = applyEdit(current.cell, edit);
    return sameCell(cell, current.cell)
      ? draft
      : withCell(draft, id, { ...current, cell });
  }
  const base = confirmed.cells.get(id);
  if (base === undefined) {
    return draft;
  }
  const previous = current?.edit ?? {};
  const next = mergeEdit(previous, edit);
  return sameCell(applyEdit(base, previous), applyEdit(base, next))
    ? draft
    : withCell(draft, id, { kind: "edit", edit: next });
}

/**
 * Create a cell with the id the client chose.
 *
 * Omitted fields take the protocol's defaults. A draft order, if any, gains
 * the cell at its placement so that it stays complete.
 */
export function createCell(
  draft: Draft,
  input: Protocol.CellInput,
  placement: Placement = {},
): Draft {
  const parsed = Protocol.CellInput.parse(input);
  const cell: CellWithSource = {
    id: parsed.id,
    code: parsed.code,
    name: parsed.name,
    config: parsed.config ?? Protocol.CellConfigInput.parse({}),
  };
  const next = withCell(draft, cell.id, { kind: "create", cell, placement });
  return draft.order === null
    ? next
    : { ...next, order: insertAt(draft.order, cell.id, placement) };
}

/** Forget an unsent creation; otherwise retain the deletion until confirmed. */
export function deleteCell(
  draft: Draft,
  id: Protocol.CellId,
  sent: Draft = EMPTY_DRAFT,
): Draft {
  const current = draft.cells.get(id);
  if (current?.kind === "delete") {
    return draft;
  }
  const next = withCell(
    draft,
    id,
    current?.kind === "create" && sent.cells.get(id)?.kind !== "create"
      ? undefined
      : { kind: "delete" },
  );
  return draft.order === null
    ? next
    : { ...next, order: draft.order.filter((other) => other !== id) };
}

/** Replace the order. Lists each cell of the document once, as `set_order` does. */
export function setOrder(
  draft: Draft,
  order: readonly Protocol.CellId[],
): Draft {
  return draft.order !== null && sameOrder(draft.order, order)
    ? draft
    : { ...draft, order: [...order] };
}

/** Drop satisfied deletions, retaining edits to missing cells for recovery. */
export function prune(
  confirmed: Document,
  draft: Draft,
  sent: Draft = EMPTY_DRAFT,
): Draft {
  let cells: Map<Protocol.CellId, CellDraft> | undefined;
  for (const [id, cell] of draft.cells) {
    if (
      cell.kind === "delete" &&
      !confirmed.cells.has(id) &&
      sent.cells.get(id)?.kind !== "create"
    ) {
      cells ??= new Map(draft.cells);
      cells.delete(id);
    }
  }
  return cells === undefined ? draft : { ...draft, cells };
}

/**
 * Release a draft after the accepted revision is present in the source.
 *
 * `sent` is the draft the accepted request was derived from. A field is
 * released when its value is still the one sent; a created cell becomes an
 * edit of whatever changed after it was sent. The model enforces the revision
 * precondition; this pure transition assumes it has already been checked.
 */
export function acknowledge(draft: Draft, sent: Draft): Draft {
  let next = draft;
  for (const [id, accepted] of sent.cells) {
    const current = next.cells.get(id);
    if (current?.kind === "delete" && accepted.kind === "delete") {
      next = withCell(next, id, undefined);
    } else if (current?.kind === "create" && accepted.kind === "create") {
      next = withEdit(next, id, editBetween(accepted.cell, current.cell));
    } else if (current?.kind === "edit" && accepted.kind === "edit") {
      next = withEdit(next, id, remainingEdit(current.edit, accepted.edit));
    }
  }
  if (
    next.order !== null &&
    sent.order !== null &&
    sameOrder(next.order, sent.order)
  ) {
    next = { ...next, order: null };
  }
  return next;
}

function withEdit(draft: Draft, id: Protocol.CellId, edit: CellEdit): Draft {
  return withCell(
    draft,
    id,
    isEmpty(edit) ? undefined : { kind: "edit", edit },
  );
}

// Projections ---------------------------------------------------------------

/** A create or edit as the edit it makes to an existing cell. */
function editOf(local: Exclude<CellDraft, { kind: "delete" }>): CellEdit {
  return local.kind === "edit" ? local.edit : local.cell;
}

/**
 * The confirmed document with a draft applied.
 *
 * A cell without a draft is the confirmed record itself, so its identity is
 * stable until the host changes it. Cells the host added since a draft order
 * was set go at the end; cells it removed leave the order.
 */
export function viewDocument(
  confirmed: Document,
  draft: Draft,
): EditableDocument {
  const cells = new Map<Protocol.CellId, EditableCell>();
  for (const [id, cell] of confirmed.cells) {
    const local = draft.cells.get(id);
    if (local?.kind === "delete") {
      continue;
    }
    cells.set(id, local === undefined ? cell : applyEdit(cell, editOf(local)));
  }
  let order: readonly Protocol.CellId[] =
    draft.order ?? confirmed.revision.order;
  for (const [id, local] of draft.cells) {
    if (local.kind === "create" && !confirmed.cells.has(id)) {
      cells.set(id, local.cell);
      if (draft.order === null) {
        order = insertAt(order, id, local.placement);
      }
    }
  }
  const placed = new Set(order);
  const unplaced = [...cells.keys()].filter((id) => !placed.has(id));
  if (unplaced.length > 0 || order.some((id) => !cells.has(id))) {
    order = [...order.filter((id) => cells.has(id)), ...unplaced];
  }
  return {
    order,
    cells,
  };
}

/**
 * The edit request that would make the host match the view.
 *
 * Preconditions are the confirmed etags. A put with no effect is left out.
 * Cells come before the order, so one request can create a cell and then
 * place it. Returns null if a put lacks source or its edited cell was removed,
 * keeping the draft atomic and retaining local intent for recovery.
 */
export function toChanges(
  confirmed: Document,
  draft: Draft,
): Protocol.Change[] | null {
  const changes: Protocol.Change[] = [];
  let stagedOrder = confirmed.revision.order;
  const stagedIds = new Set(stagedOrder);
  for (const [id, local] of draft.cells) {
    const base = confirmed.cells.get(id);
    if (local.kind === "delete") {
      if (base !== undefined) {
        changes.push({ kind: "delete_cell", id, base_etag: base.etag });
        stagedOrder = stagedOrder.filter((other) => other !== id);
        stagedIds.delete(id);
      }
    } else if (local.kind === "create") {
      const anchor = local.placement.after ?? local.placement.before;
      const placement =
        anchor === undefined || stagedIds.has(anchor) ? local.placement : {};
      changes.push({
        kind: "put_cell",
        base_etag: null,
        cell: local.cell,
        ...placement,
      });
      if (base === undefined) {
        stagedOrder = insertAt(stagedOrder, id, placement);
        stagedIds.add(id);
      }
    } else if (base !== undefined) {
      const cell = applyEdit(base, local.edit);
      if (!sameCell(base, cell)) {
        const { code } = cell;
        if (code === null) {
          return null;
        }
        changes.push({
          kind: "put_cell",
          base_etag: base.etag,
          cell: { ...cell, code },
        });
      }
    } else {
      return null;
    }
  }
  const { order } = viewDocument(confirmed, draft);
  if (
    (draft.order !== null && !sameOrder(order, confirmed.revision.order)) ||
    !sameOrder(order, stagedOrder)
  ) {
    changes.push({
      kind: "set_order",
      base_etag: confirmed.revision.order_etag,
      order: [...order],
    });
  }
  return changes;
}
