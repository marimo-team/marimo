/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import {
  createNotebookReducer,
  type NotebookEvent,
  NotebookEvents,
  type NotebookTransport,
  StreamStopped,
} from "@marimo-team/client";
import type { Attachment, NotebookOutput } from "@marimo-team/client/protocol";
import { type Atom, atom, type createStore } from "jotai/vanilla";
import { z } from "zod";
import {
  ConnectionClosedReason,
  ConnectionState,
  type ConnectionStatus,
} from "./connection";
import { attachments } from "./resources/attachments";
import { type Document, document } from "./resources/document";

/** The kinds the editor reads, with marimo's own notifications. */
const TYPES = ["notebook", "cell", "document", "attachment", "marimo"] as const;

type EditorEvent = NotebookEvent<(typeof TYPES)[number]>;

/** A native marimo notification, passed through without interpretation. */
const MarimoMessage = z.object({ marimo: z.unknown() });

/** A connection to a notebook on a marimo host. */
export interface NotebookClient {
  /** Client connection status, independent of application session readiness. */
  readonly connectionAtom: Atom<ConnectionStatus>;
  /** Identity and capabilities, available while the stream is connected and ready. */
  readonly notebookAtom: Atom<NotebookOutput | null>;
  /**
   * The most recently confirmed document.
   *
   * Null until a snapshot is complete, after reset or removal, and on
   * connections without host document events. A temporary disconnection
   * retains the last document. Partial updates are not exposed.
   */
  readonly documentAtom: Atom<Document | null>;
  /** Live attachments, empty until the stream is ready or while disconnected. */
  readonly attachmentsAtom: Atom<readonly Attachment[]>;
  /** Attempt to restore a closed connection after checking host health. */
  reconnect(): Promise<void>;
}

/** The transport and application callbacks needed to follow a notebook. */
export interface NotebookConnection {
  /** Opens one connection to the notebook's stream. */
  transport: NotebookTransport;
  /** Abort to close the stream and clear the client's state. */
  signal: AbortSignal;
  /** Check whether the host is reachable before an explicit reconnect. */
  checkHealth: () => Promise<boolean>;
  /** Handle a native marimo notification. Its payload has not been validated. */
  onNotification: (notification: unknown) => void;
}

const disconnected = {
  state: ConnectionState.CLOSED,
  code: ConnectionClosedReason.KERNEL_DISCONNECTED,
  reason: "kernel not found",
} satisfies ConnectionStatus;

const malformed = {
  ...disconnected,
  reason: "Failed to decode notebook message",
} satisfies ConnectionStatus;

function isStatus(value: unknown): value is ConnectionStatus {
  return typeof value === "object" && value !== null && "state" in value;
}

/**
 * The status to show after the stream stopped.
 *
 * A transport says which status its stop means. An event the protocol
 * rejects is malformed. Anything else means the host was not reached.
 */
function statusAfter(error: unknown): ConnectionStatus {
  if (error instanceof StreamStopped && isStatus(error.cause)) {
    return error.cause;
  }
  if (error instanceof StreamStopped && error.cause instanceof z.ZodError) {
    return malformed;
  }
  return disconnected;
}

/** Create a client without opening a connection. */
export function createNotebookClient(store: ReturnType<typeof createStore>) {
  // `useNotebookSession` copies this into the editor's shared `connectionAtom`,
  // which gates features until MO-8051 derives availability separately.
  const connectionAtom = atom<ConnectionStatus>({
    state: ConnectionState.NOT_STARTED,
  });
  // One atom holds the whole stream, which resource atoms derive from.
  const reducer = createNotebookReducer({ document, attachments });
  const streamAtom = atom(reducer.initial);
  // A resumed stream is live, but presence waits for this connection's ready.
  const readyAtom = atom(false);
  const presentAtom = atom(
    (get) =>
      get(readyAtom) && get(connectionAtom).state === ConnectionState.OPEN,
  );
  const notebookAtom = atom((get) =>
    get(presentAtom) ? get(streamAtom).notebook : null,
  );
  const documentAtom = atom(
    (get) => get(streamAtom).resources.document.current,
  );
  const attachmentsAtom = atom((get) =>
    get(presentAtom)
      ? get(streamAtom).resources.attachments
      : attachments.initial,
  );
  let reconnect: (() => Promise<void>) | undefined;
  const client: NotebookClient = {
    connectionAtom,
    notebookAtom,
    documentAtom,
    attachmentsAtom,
    reconnect: async () => reconnect?.(),
  };

  function setStatus(status: ConnectionStatus) {
    store.set(readyAtom, false);
    store.set(connectionAtom, status);
  }

  function connect({
    transport,
    signal,
    checkHealth,
    onNotification,
  }: NotebookConnection) {
    if (signal.aborted) {
      return;
    }
    let events: NotebookEvents<(typeof TYPES)[number]> | undefined;
    let checkingHealth = false;
    // Whether the replica still holds the state the last cursor describes.
    let resumable = true;

    /** Mirror one stream into the atoms until it closes. */
    function follow(cursor?: string) {
      resumable = true;
      const current = new NotebookEvents(transport, {
        types: TYPES,
        cursor,
        signal,
        // TODO(MO-8051): Gate editing and running on the notebook's operations
        // and request results instead. The stream's status would then only
        // mark the view as stale.
        onStatus: (status) => {
          if (status === "connecting") {
            setStatus({ state: ConnectionState.CONNECTING });
          } else if (status === "connected") {
            setStatus({ state: ConnectionState.OPEN });
          }
        },
      });
      current.subscribe(
        (event) => apply(current, event),
        (error) => {
          if (!signal.aborted && current === events) {
            Logger.warn("Notebook stream stopped", error);
            setStatus(statusAfter(error));
          }
        },
      );
      events = current;
    }

    function apply(source: NotebookEvents<string>, event: EditorEvent) {
      if (event.event === "marimo") {
        const message = MarimoMessage.safeParse(event.data);
        if (message.success) {
          onNotification(message.data.marimo);
        } else {
          Logger.error("Failed to decode notebook message", event);
        }
        return;
      }
      try {
        store.set(streamAtom, reducer.reduce(store.get(streamAtom), event));
      } catch (error) {
        // An event the replica cannot apply, such as another notebook's.
        Logger.error("Failed to apply notebook event", error);
        source.close();
        resumable = false;
        store.set(streamAtom, reducer.initial);
        setStatus(malformed);
        return;
      }
      if (event.event === "ready" || event.event === "reset") {
        store.set(readyAtom, event.event === "ready");
      }
    }

    reconnect = async () => {
      if (signal.aborted || checkingHealth || events?.status !== "closed") {
        return;
      }
      checkingHealth = true;
      setStatus({ state: ConnectionState.CONNECTING });
      try {
        const healthy = await checkHealth();
        if (signal.aborted) {
          return;
        }
        if (!healthy) {
          setStatus(disconnected);
          return;
        }
        follow(resumable ? (events.cursor ?? undefined) : undefined);
      } catch (error) {
        if (!signal.aborted) {
          Logger.error("Notebook health check failed", error);
          setStatus(disconnected);
        }
      } finally {
        checkingHealth = false;
      }
    };

    signal.addEventListener(
      "abort",
      () => {
        reconnect = undefined;
        store.set(streamAtom, reducer.initial);
        setStatus({ state: ConnectionState.NOT_STARTED });
      },
      { once: true },
    );

    setStatus({ state: ConnectionState.CONNECTING });
    follow();
  }

  return { client, connect };
}
