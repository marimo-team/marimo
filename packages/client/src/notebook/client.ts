/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "../protocol.ts";
import type { NotebookKind } from "../kinds.ts";
import {
  below,
  type CallTarget,
  type ClientOptions,
  type MutationOptions,
  type OperationCall,
  type OperationsBelow,
  request,
  type Result,
  type Target,
} from "../request.ts";
import { NotebookEvents, type NotebookEventsOptions } from "./events.ts";

/** How a `NotebookClient` reaches and authenticates with its host. */
export type NotebookClientOptions = ClientOptions;

/** Options for a request the host may need decisions for. */
interface DecisionOptions extends MutationOptions {
  /** Answers to the decisions a `decision-required` problem asked for. */
  readonly decisions?: Readonly<Record<string, string>>;
}

/** Options for saving a notebook. */
interface SaveOptions extends DecisionOptions {
  /** The document etag the client last read. A different etag is a conflict. */
  readonly ifMatch?: string;
}

type Scope = "/notebooks/{notebook_id}";

type NotebookOperationId = OperationsBelow<Scope>;

/**
 * A notebook operation as one message, the parts of its request without a URL.
 *
 * `unstable_NotebookCall` is any notebook operation, and
 * `unstable_NotebookCall<"notebook.edit">` is one. Header names are lowercase.
 *
 * @experimental The shape may change while transports other than HTTP settle.
 */
export type unstable_NotebookCall<
  Id extends NotebookOperationId = NotebookOperationId,
> = OperationCall<Id>;

/** The notebook's operations, sent to whichever target the client was given. */
class NotebookOperations {
  readonly #target: Target<Scope> | CallTarget<Scope>;

  public constructor(target: Target<Scope> | CallTarget<Scope>) {
    this.#target = target;
  }

  /** Rename or move the notebook. */
  public update(
    changes: Protocol.UpdateNotebookRequest,
    options?: MutationOptions,
  ): Promise<Result<Protocol.NotebookOutput>> {
    return this.#send("notebook.update", { body: changes, options });
  }

  /** Delete the notebook. */
  public delete(options?: MutationOptions): Promise<Result<undefined>> {
    return this.#send("notebook.delete", { options });
  }

  /** Ask the host for a URL that opens the notebook for people. */
  public open(
    options?: MutationOptions,
  ): Promise<Result<Protocol.OpenNotebookResponseOutput>> {
    return this.#send("notebook.open", { options });
  }

  /** Apply changes to the document as one unit. */
  public edit(
    changes: readonly Protocol.Change[],
    options?: MutationOptions,
  ): Promise<Result<Protocol.EditResponseOutput>> {
    return this.#send("notebook.edit", {
      body: { changes: [...changes] },
      options,
    });
  }

  /** Write the document to the notebook's store. */
  public save(
    options?: SaveOptions,
  ): Promise<Result<Protocol.EditResponseOutput>> {
    return this.#send("notebook.save", {
      body: { decisions: options?.decisions },
      headers: { "If-Match": options?.ifMatch },
      options,
    });
  }

  /** Start a runtime for the notebook. */
  public start(
    options?: DecisionOptions,
  ): Promise<Result<Protocol.RuntimeOutput>> {
    return this.#send("runtime.start", {
      body: { decisions: options?.decisions },
      options,
    });
  }

  /** Stop the notebook's runtime. */
  public stop(
    options?: MutationOptions,
  ): Promise<Result<Protocol.RuntimeOutput>> {
    return this.#send("runtime.stop", { options });
  }

  /** Restart the notebook's runtime. */
  public restart(
    options?: MutationOptions,
  ): Promise<Result<Protocol.RuntimeOutput>> {
    return this.#send("runtime.restart", { options });
  }

  /** Run cells or scratch code in the notebook's runtime. */
  public run(
    request: Protocol.RunRequest,
    options?: MutationOptions,
  ): Promise<Result<Protocol.RunOutput>> {
    return this.#send("runtime.run", { body: request, options });
  }

  /** Interrupt a run. */
  public interrupt(
    runId: Protocol.RunId,
    options?: MutationOptions,
  ): Promise<Result<Protocol.RunOutput>> {
    return this.#send("runtime.interrupt", {
      params: { run_id: runId },
      options,
    });
  }

  #send<Id extends OperationsBelow<Scope>>(
    id: Id,
    call: Parameters<typeof request<Scope, Id>>[2],
  ) {
    return request(this.#target, id, call);
  }
}

/**
 * A client for one notebook.
 *
 * Requests go to URLs below the notebook's URL and keep its query string.
 */
export class NotebookClient extends NotebookOperations {
  readonly #url: URL;
  readonly #options: NotebookClientOptions;

  public constructor(url: string | URL, init: NotebookClientOptions = {}) {
    const notebook = new URL(url);
    super({ url: notebook, prefix: "/notebooks/{notebook_id}", client: init });
    this.#url = notebook;
    this.#options = init;
  }

  /**
   * A client whose requests go to `send` as calls rather than over HTTP.
   *
   * `send` delivers each call and resolves with the host's reply, a status
   * and a body. Replies are validated as HTTP responses are. The client has
   * no URL, so it has no `url` or `events`.
   *
   * @experimental The shape may change while transports other than HTTP settle.
   */
  public static unstable_over(
    send: (call: unstable_NotebookCall) => Promise<unknown>,
    { notebookId }: { readonly notebookId: string },
  ): Omit<NotebookClient, "url" | "events"> {
    return new NotebookOperations({
      // SAFETY: `request` builds each message from its operation's table
      // entry. Its params fill the path's placeholders, its headers are the
      // entry's headers in lowercase, and its body is parsed by the entry's
      // schema, which is the shape `unstable_NotebookCall` gives that
      // operation. The tests check the message for each method.
      send: (message) => send(message as unstable_NotebookCall),
      prefix: "/notebooks/{notebook_id}",
      params: { notebook_id: notebookId },
    });
  }

  /**
   * The notebook's URL, such as `…/api/marimo/v1/notebooks/n1`.
   *
   * Each read returns a copy, so changing it does not redirect requests.
   */
  public get url(): URL {
    return new URL(this.#url);
  }

  /**
   * Follow the notebook's stream.
   *
   * The stream is served below the notebook's URL over server-sent events,
   * and shares this client's options.
   */
  public events<const K extends string = NotebookKind>(
    options: Omit<NotebookEventsOptions<K>, keyof ClientOptions> = {},
  ): NotebookEvents<K> {
    return new NotebookEvents<K>(below(this.#url, "/events"), {
      ...this.#options,
      ...options,
    });
  }
}
