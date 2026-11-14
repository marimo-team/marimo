/* Copyright 2026 Marimo. All rights reserved. */

/** What a backend's stream has confirmed about a notebook, kept in atoms. */

import { Logger } from "@/utils/Logger";
import {
  createNotebookReducer,
  type NotebookEvent,
  NotebookEvents,
  StreamStopped,
} from "@marimo-team/client";
import type {
  Attachment,
  NotebookOutput,
  Runtime,
} from "@marimo-team/client/protocol";
import { type Atom, atom, type createStore } from "jotai/vanilla";
import { z } from "zod";
import type { NotebookBackend } from "./backend";
import {
  ConnectionClosedReason,
  ConnectionState,
  type ConnectionStatus,
} from "./connection";
import { attachments } from "./resources/attachments";
import { type Document, document } from "./resources/document";
import { type Executions, executions } from "./resources/executions";
import { type Results, results } from "./resources/results";
import { runtime } from "./resources/runtime";

/**
 * The kinds the editor reads, with marimo's own notifications.
 *
 * Console and display items stay out until the editor reads outputs from
 * the replica. The native notifications still carry them.
 */
const TYPES = [
  "notebook",
  "cell",
  "document",
  "attachment",
  "runtime",
  "run",
  "execution",
  "input",
  "variable",
  "marimo",
] as const;

type EditorEvent = NotebookEvent<(typeof TYPES)[number]>;

/** A native marimo notification, passed through without interpretation. */
const MarimoMessage = z.object({ marimo: z.unknown() });

/** A notebook as its backend's stream reports it, kept current while connected. */
export interface NotebookReplica {
  /** Connection status, independent of application session readiness. */
  readonly connectionAtom: Atom<ConnectionStatus>;
  /** Identity and capabilities, available while the stream is connected and ready. */
  readonly notebookAtom: Atom<NotebookOutput | null>;
  /**
   * The most recently confirmed document.
   *
   * Null until a snapshot is complete, after removal, and on connections
   * without host document events. A temporary disconnection retains the
   * last document, and so does a reset, until the snapshot that follows
   * it is complete. Partial updates are not exposed.
   */
  readonly documentAtom: Atom<Document | null>;
  /**
   * The backend this replica follows, or null while not connected.
   *
   * Its commands reach the host that confirmed `documentAtom`. A temporary
   * disconnection keeps it. Connecting again or disconnecting replaces it.
   */
  readonly backendAtom: Atom<NotebookBackend | null>;
  /** Live attachments, empty until the stream is ready or while disconnected. */
  readonly attachmentsAtom: Atom<readonly Attachment[]>;
  /** The notebook's runtime, null while it has none or the stream is not ready. */
  readonly runtimeAtom: Atom<Runtime | null>;
  /**
   * Runs and executions as the stream reports them.
   *
   * Visible as events arrive, including during a snapshot, so a consumer
   * joins with `documentAtom`, which is null until the snapshot is ready.
   * Kept across a temporary disconnection and through a reset, like the
   * document, and cleared on removal.
   */
  readonly executionsAtom: Atom<Executions>;
  /** Each document cell's last completed execution record, kept while it runs again. */
  readonly resultsAtom: Atom<Results>;
  /**
   * Follow a backend, replacing any current connection.
   *
   * The returned function ends this connection and clears the replica.
   * It does nothing once another connection has replaced this one.
   */
  connect(
    backend: NotebookBackend,
    options: {
      /** Handle a native marimo notification. Its payload has not been validated. */
      onNotification: (notification: unknown) => void;
    },
  ): () => void;
  /** Restore the current connection after its stream closed, if the host is healthy. */
  reconnect(): Promise<void>;
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

/** Create a replica without connecting it. */
export function createNotebookReplica(
  store: ReturnType<typeof createStore>,
): NotebookReplica {
  // `useNotebookSession` copies this into the editor's shared `connectionAtom`,
  // which gates features until MO-8051 derives availability separately.
  const connectionAtom = atom<ConnectionStatus>({
    state: ConnectionState.NOT_STARTED,
  });
  // One atom holds the whole stream, which resource atoms derive from.
  const reducer = createNotebookReducer({
    document,
    attachments,
    runtime,
    executions,
    results,
  });
  const streamAtom = atom(reducer.initial);
  const presentAtom = atom(
    (get) =>
      get(streamAtom).phase === "live" &&
      get(connectionAtom).state === ConnectionState.OPEN,
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
  const runtimeAtom = atom((get) =>
    get(presentAtom) ? get(streamAtom).resources.runtime : null,
  );
  const executionsAtom = atom((get) => get(streamAtom).resources.executions);
  const resultsAtom = atom((get) => get(streamAtom).resources.results);
  const backendAtom = atom<NotebookBackend | null>(null);
  /** The connection this replica follows. Connecting again ends it. */
  let current: { end(): void; reconnect(): Promise<void> } | undefined;

  function setStatus(status: ConnectionStatus) {
    if (status.state === ConnectionState.CONNECTING) {
      store.set(streamAtom, reducer.resume(store.get(streamAtom)));
    }
    store.set(connectionAtom, status);
  }

  /** Drop what the stream reported and show `status`. */
  function clear(status: ConnectionStatus) {
    store.set(streamAtom, reducer.initial);
    setStatus(status);
  }

  return {
    connectionAtom,
    notebookAtom,
    documentAtom,
    backendAtom,
    attachmentsAtom,
    runtimeAtom,
    executionsAtom,
    resultsAtom,
    connect,
    reconnect: async () => current?.reconnect(),
  };

  function connect(
    connected: NotebookBackend,
    { onNotification }: { onNotification: (notification: unknown) => void },
  ) {
    current?.end();
    const lifetime = new AbortController();
    const { signal } = lifetime;
    const checkHealth = connected.checkHealth ?? (async () => true);
    store.set(backendAtom, connected);
    const { transport } = connected;
    let events: NotebookEvents<(typeof TYPES)[number]> | undefined;
    let checkingHealth = false;
    /**
     * The snapshot that follows a reset, built out of sight until it is
     * ready.
     *
     * A host resets a stream it cannot resume, and a transport resets
     * one whose session changed. Publishing the new snapshot as it
     * arrives would empty every reader for as long as that takes. What
     * was on show stays instead, as it does while disconnected: the
     * document and results remain, and the notebook is not present until
     * the replacement is complete.
     */
    let rebuilding: typeof reducer.initial | undefined;

    /** Mirror one stream into the atoms until it closes. */
    function follow(cursor?: string) {
      rebuilding = undefined;
      if (cursor === undefined) {
        if (store.get(streamAtom).phase === "snapshot") {
          store.set(streamAtom, reducer.initial);
        } else {
          rebuilding = reducer.initial;
        }
      }
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
            const status = statusAfter(error);
            if (status === malformed) {
              stopMalformed(current);
            } else {
              setStatus(status);
            }
          }
        },
      );
      events = current;
    }

    function stopMalformed(source: NotebookEvents<string>) {
      source.close();
      rebuilding = undefined;
      // The cursor can already include an event the replica rejected.
      clear(malformed);
    }

    function apply(source: NotebookEvents<string>, event: EditorEvent) {
      if (event.event === "marimo") {
        const message = MarimoMessage.safeParse(event.data);
        if (message.success) {
          onNotification(message.data.marimo);
        } else {
          Logger.error("Failed to decode notebook message", event);
          stopMalformed(source);
        }
        return;
      }
      try {
        const shown = store.get(streamAtom);
        if (rebuilding !== undefined) {
          rebuilding = reducer.reduce(rebuilding, event);
          if (rebuilding.phase !== "snapshot") {
            store.set(streamAtom, rebuilding);
            rebuilding = undefined;
          }
        } else if (event.event === "reset" && shown.phase !== "snapshot") {
          rebuilding = reducer.reduce(shown, event);
          store.set(streamAtom, reducer.resume(shown));
        } else {
          store.set(streamAtom, reducer.reduce(shown, event));
        }
      } catch (error) {
        // An event the replica cannot apply, such as another notebook's.
        Logger.error("Failed to apply notebook event", error);
        stopMalformed(source);
        return;
      }
    }

    const reconnect = async () => {
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
        follow(
          store.get(streamAtom).phase === "snapshot"
            ? undefined
            : (events.cursor ?? undefined),
        );
      } catch (error) {
        if (!signal.aborted) {
          Logger.error("Notebook health check failed", error);
          setStatus(disconnected);
        }
      } finally {
        checkingHealth = false;
      }
    };

    const connection = {
      end: () => {
        if (signal.aborted) {
          return;
        }
        lifetime.abort();
        if (current === connection) {
          current = undefined;
          store.set(backendAtom, null);
        }
        clear({ state: ConnectionState.NOT_STARTED });
      },
      reconnect,
    };
    current = connection;
    setStatus({ state: ConnectionState.CONNECTING });
    follow();
    return connection.end;
  }
}
