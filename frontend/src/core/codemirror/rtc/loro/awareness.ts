/* Copyright 2024 Marimo. All rights reserved. */

import {
  Annotation,
  EditorSelection,
  type Extension,
  type SelectionRange,
  StateEffect,
  StateField,
} from "@codemirror/state";
import {
  Direction,
  EditorView,
  type LayerMarker,
  layer,
  type PluginValue,
  type Rect,
  RectangleMarker,
  type ViewUpdate,
} from "@codemirror/view";
import {
  type Awareness,
  type AwarenessListener,
  Cursor,
  type LoroDoc,
  type LoroText,
  type PeerID,
  type Subscription,
} from "loro-crdt";
import type { TypedString } from "@/utils/typed";

export type ScopeId = TypedString<"loro:scope">;
export type Uid = TypedString<"loro:uid"> | PeerID;

export const loroCursorTheme = EditorView.baseTheme({
  ".loro-cursor": {
    position: "absolute",
    width: "2px",
    display: "inline-block",
    height: "1.2em",
  },
  ".loro-cursor::before": {
    position: "absolute",
    top: "1.3em",
    left: "0",
    content: "var(--rtc-name)",
    padding: "2px 6px",
    fontSize: "12px",
    borderRadius: "3px",
    whiteSpace: "nowrap",
    userSelect: "none",
    backgroundColor: "inherit",
    opacity: "0.7",
  },
  ".loro-selection": {
    opacity: "0.5",
  },
});

export type AwarenessState =
  | {
      type: "update";
      uid: Uid;
      scopeId: ScopeId;
      cursor: { anchor: Uint8Array; head?: Uint8Array };
      user?: {
        name: string;
        colorClassName: string;
      };
    }
  | {
      type: "delete";
      uid: Uid;
      scopeId: ScopeId;
    };

export interface UserState {
  name: string;
  colorClassName: string;
}

type CursorEffect =
  | {
      type: "update";
      peer: Uid;
      scopeId: ScopeId;
      cursor: { anchor: number; head?: number };
      user?: UserState;
    }
  | {
      type: "delete";
      peer: Uid;
      scopeId: ScopeId;
    }
  | {
      type: "checkout";
      checkout: boolean;
    };

// We should use layer https://github.com/codemirror/dev/issues/989
export const remoteAwarenessAnnotation = Annotation.define<undefined>();
export const remoteAwarenessEffect = StateEffect.define<CursorEffect>();
export const remoteAwarenessStateField = StateField.define<{
  remoteCursors: Map<string, CursorPosition>;
  isCheckout: boolean;
}>({
  create() {
    return { remoteCursors: new Map(), isCheckout: false };
  },
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(remoteAwarenessEffect)) {
        switch (effect.value.type) {
          case "update": {
            const { peer: uid, user, cursor } = effect.value;
            value.remoteCursors.set(uid, {
              uid,
              cursor,
              user,
            });
            break;
          }
          case "delete":
            value.remoteCursors.delete(effect.value.peer);
            break;
          case "checkout":
            value.isCheckout = effect.value.checkout;
        }
      }
    }
    return value;
  },
});

const isRemoteCursorUpdate = (update: ViewUpdate): boolean => {
  const effect = update.transactions
    .flatMap((transaction) => transaction.effects)
    .filter((effect) => effect.is(remoteAwarenessEffect));
  return update.docChanged || update.viewportChanged || effect.length > 0;
};

export const createCursorLayer = (): Extension => {
  return layer({
    above: true,
    class: "loro-cursor-layer",
    update: isRemoteCursorUpdate,
    markers: (view) => {
      const { remoteCursors: remoteStates, isCheckout } = view.state.field(
        remoteAwarenessStateField,
      );
      if (isCheckout) {
        return [];
      }
      return [...remoteStates.values()].flatMap((state) => {
        const selectionRange = EditorSelection.cursor(state.cursor.anchor);
        return RemoteCursorMarker.createCursor(
          view,
          selectionRange,
          state.user?.name || "unknown",
          state.user?.colorClassName || "",
        );
      });
    },
  });
};

export const createSelectionLayer = (): Extension =>
  layer({
    above: false,
    class: "loro-selection-layer",
    update: isRemoteCursorUpdate,
    markers: (view) => {
      const { remoteCursors: remoteStates, isCheckout } = view.state.field(
        remoteAwarenessStateField,
      );
      if (isCheckout) {
        return [];
      }
      return [...remoteStates.entries()]
        .filter(
          ([, state]) =>
            state.cursor.head !== undefined &&
            state.cursor.anchor !== state.cursor.head,
        )
        .flatMap(([, state]) => {
          const selectionRange = EditorSelection.range(
            state.cursor.anchor,
            // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
            state.cursor.head!,
          );
          const markers = RectangleMarker.forRange(
            view,
            `loro-selection ${state.user?.colorClassName || ""}`,
            selectionRange,
          );
          return markers;
        });
    },
  });

/**
 * Renders a blinking cursor to indicate the cursor of another user.
 */
export class RemoteCursorMarker implements LayerMarker {
  constructor(
    private left: number,
    private top: number,
    private height: number,
    private name: string,
    private colorClassName: string,
  ) {}

  draw(): HTMLElement {
    const elt = document.createElement("div");
    this.adjust(elt);
    return elt;
  }

  update(elt: HTMLElement): boolean {
    this.adjust(elt);
    return true;
  }

  adjust(element: HTMLElement) {
    element.style.left = `${this.left}px`;
    element.style.top = `${this.top}px`;
    element.style.height = `${this.height}px`;
    element.className = `loro-cursor ${this.colorClassName}`;
    element.style.setProperty("--rtc-name", `"${this.name}"`);
  }

  eq(other: RemoteCursorMarker): boolean {
    return (
      this.left === other.left &&
      this.top === other.top &&
      this.height === other.height &&
      this.name === other.name
    );
  }

  public static createCursor(
    view: EditorView,
    position: SelectionRange,
    displayName: string,
    colorClassName: string,
  ): RemoteCursorMarker[] {
    const absolutePosition = RemoteCursorMarker.calculateAbsoluteCursorPosition(
      position,
      view,
    );
    if (!absolutePosition) {
      return [];
    }
    const rect = view.scrollDOM.getBoundingClientRect();
    const left =
      view.textDirection === Direction.LTR
        ? rect.left
        : rect.right - view.scrollDOM.clientWidth;
    const baseLeft = left - view.scrollDOM.scrollLeft;
    const baseTop = rect.top - view.scrollDOM.scrollTop;
    return [
      new RemoteCursorMarker(
        absolutePosition.left - baseLeft,
        absolutePosition.top - baseTop,
        absolutePosition.bottom - absolutePosition.top,
        displayName,
        colorClassName,
      ),
    ];
  }

  private static calculateAbsoluteCursorPosition(
    position: SelectionRange,
    view: EditorView,
  ): Rect | null {
    const cappedPositionHead = Math.max(
      0,
      Math.min(view.state.doc.length, position.anchor),
    );
    return view.coordsAtPos(cappedPositionHead, position.assoc || 1);
  }
}

const parseAwarenessUpdate = (
  doc: LoroDoc,
  awareness: Awareness<AwarenessState>,
  arg: {
    updated: PeerID[];
    added: PeerID[];
    removed: PeerID[];
  },
  scopeId: ScopeId,
): Array<StateEffect<CursorEffect>> => {
  const effects = [];
  const { updated, added } = arg;
  for (const update of [...updated, ...added]) {
    const effect = getEffects(doc, awareness, update, scopeId);
    if (effect) {
      effects.push(effect);
    }
  }
  return effects;
};

const getEffects = (
  doc: LoroDoc,
  awareness: Awareness<AwarenessState>,
  peer: PeerID,
  scopeId: ScopeId,
): StateEffect<CursorEffect> | undefined => {
  const states = awareness.getAllStates();
  const state = states[peer];
  if (!state) {
    return;
  }
  if (peer === doc.peerIdStr) {
    return;
  }
  if (state.scopeId !== scopeId) {
    return;
  }

  if (state.type === "delete") {
    return remoteAwarenessEffect.of({
      type: "delete",
      peer: state.uid,
      scopeId: state.scopeId,
    });
  }

  const anchor = Cursor.decode(state.cursor.anchor);
  const anchorPos = doc.getCursorPos(anchor).offset;
  let headPos = anchorPos;
  if (state.cursor.head) {
    // range
    const head = Cursor.decode(state.cursor.head);
    headPos = doc.getCursorPos(head).offset;
  }
  return remoteAwarenessEffect.of({
    type: "update",
    peer: state.uid,
    scopeId: state.scopeId,
    cursor: { anchor: anchorPos, head: headPos },
    user: state.user,
  });
};

export interface CursorPosition {
  uid: string;
  cursor: { anchor: number; head?: number };
  user?: UserState;
}

export class AwarenessPlugin implements PluginValue {
  sub: Subscription;

  constructor(
    public view: EditorView,
    public doc: LoroDoc,
    public user: UserState,
    public awareness: Awareness<AwarenessState>,
    private getTextFromDoc: (doc: LoroDoc) => LoroText,
    private scopeId: ScopeId,
    private getUserId?: () => Uid,
  ) {
    this.sub = this.doc.subscribe((e) => {
      if (e.by === "local") {
        // update remote cursor position
        const effects = [];
        for (const peer of this.awareness.peers()) {
          const effect = getEffects(
            this.doc,
            this.awareness,
            peer,
            this.scopeId,
          );
          if (effect) {
            effects.push(effect);
          }
        }
        this.view.dispatch({
          effects,
        });
      } else if (e.by === "checkout") {
        // TODO: better way
        this.view.dispatch({
          effects: [
            remoteAwarenessEffect.of({
              type: "checkout",
              checkout: this.doc.isDetached(),
            }),
          ],
        });
      }
    });
  }

  update(update: ViewUpdate): void {
    if (!update.selectionSet && !update.focusChanged && !update.docChanged) {
      return;
    }
    const selection = update.state.selection.main;
    if (this.view.hasFocus && !this.doc.isDetached()) {
      const cursorState = getCursorState(
        this.doc,
        this.getTextFromDoc,
        selection.anchor,
        selection.head,
      );
      this.awareness.setLocalState({
        type: "update",
        uid: this.getUserId ? this.getUserId() : this.doc.peerIdStr,
        scopeId: this.scopeId,
        cursor: cursorState,
        user: this.user,
      });
    } else {
      // when checkout or blur
      this.awareness.setLocalState({
        type: "delete",
        uid: this.getUserId ? this.getUserId() : this.doc.peerIdStr,
        scopeId: this.scopeId,
      });
    }
  }

  destroy(): void {
    this.sub?.();
    this.awareness.setLocalState({
      type: "delete",
      uid: this.getUserId ? this.getUserId() : this.doc.peerIdStr,
      scopeId: this.scopeId,
    });
  }
}
export class RemoteAwarenessPlugin implements PluginValue {
  _awarenessListener?: AwarenessListener;
  constructor(
    public view: EditorView,
    public doc: LoroDoc,
    public awareness: Awareness<AwarenessState>,
    private scopeId: ScopeId,
  ) {
    const listener: AwarenessListener = async (arg, origin) => {
      if (origin === "local") {
        return;
      }
      this.view.dispatch({
        effects: parseAwarenessUpdate(
          this.doc,
          this.awareness,
          arg,
          this.scopeId,
        ),
      });
    };
    this._awarenessListener = listener;
    this.awareness.addListener(listener);
  }

  destroy(): void {
    if (this._awarenessListener) {
      this.awareness.removeListener(this._awarenessListener);
    }
  }
}

const getCursorState = (
  doc: LoroDoc,
  getTextFromDoc: (doc: LoroDoc) => LoroText,
  anchor: number,
  head: number | undefined,
) => {
  if (anchor === head) {
    head = undefined;
  }
  const anchorCursor = getTextFromDoc(doc).getCursor(anchor)?.encode();

  if (!anchorCursor) {
    throw new Error("cursor head not found");
  }
  let headCursor: Uint8Array | undefined;
  if (head !== undefined) {
    headCursor = getTextFromDoc(doc).getCursor(head)?.encode();
  }

  return {
    anchor: anchorCursor,
    head: headCursor,
  };
};
