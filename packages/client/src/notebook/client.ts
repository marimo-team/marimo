/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "../protocol.ts";
import type { Kind } from "../reducer.ts";
import {
  below,
  type Connection,
  type MutationOptions,
  type OperationsBelow,
  request,
  type Result,
  type Target,
} from "../request.ts";
import { NotebookEvents, type NotebookEventsInit } from "./events.ts";

/** How a `NotebookClient` reaches and authenticates with its host. */
export type NotebookClientInit = Connection;

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

/**
 * A client for one notebook.
 *
 * Requests go to URLs below the notebook's URL and keep its query string.
 */
export class NotebookClient {
  readonly #url: URL;
  readonly #target: Target<Scope>;

  public constructor(url: string | URL, init: NotebookClientInit = {}) {
    this.#url = new URL(url);
    this.#target = {
      url: this.#url,
      prefix: "/notebooks/{notebook_id}",
      connection: init,
    };
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
   * and shares this client's connection.
   */
  public events<const K extends string = Kind>(
    options: Omit<NotebookEventsInit<K>, keyof Connection> = {},
  ): NotebookEvents<K> {
    return new NotebookEvents<K>(below(this.#url, "/events"), {
      ...this.#target.connection,
      ...options,
    });
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
