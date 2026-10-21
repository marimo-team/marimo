/* Copyright 2026 Marimo. All rights reserved. */

import { CatalogEvents, type CatalogEventsInit } from "./catalog/events.ts";
import type { CatalogKind } from "./kinds.ts";
import { NotebookClient } from "./notebook/client.ts";
import type * as Protocol from "./protocol.ts";
import {
  below,
  type Connection,
  type MutationOptions,
  request,
  resolve,
  type Result,
  type Target,
} from "./request.ts";

/** How a `Client` reaches and authenticates with its host. */
export type ClientInit = Connection;

/** A client for a host's API, without a retained catalog. */
export class Client {
  readonly #target: Target<"">;

  public constructor(url: string | URL, init: ClientInit = {}) {
    this.#target = { url: new URL(url), prefix: "", connection: init };
  }

  /** The host API's base URL. Each read returns a copy. */
  public get url(): URL {
    return new URL(this.#target.url);
  }

  /** Follow the catalog with this client's connection and an independent cursor. */
  public events<const K extends CatalogKind = CatalogKind>(
    options: Omit<CatalogEventsInit<K>, keyof Connection> = {},
  ): CatalogEvents<K> {
    return new CatalogEvents<K>(below(this.#target.url, "/events"), {
      ...this.#target.connection,
      ...options,
    });
  }

  /**
   * Address a notebook by id or catalog record, sharing this connection.
   *
   * Makes no request and retains no metadata. The id belongs to this host.
   */
  public notebook(
    notebook: Protocol.NotebookId | Pick<Protocol.NotebookOutput, "id">,
  ): NotebookClient {
    const id = typeof notebook === "string" ? notebook : notebook.id;
    return new NotebookClient(
      resolve(this.#target, "/notebooks/{notebook_id}", { notebook_id: id }),
      this.#target.connection,
    );
  }

  /** Create a notebook. Its record also arrives on the catalog stream. */
  public createNotebook(
    notebook: Protocol.CreateNotebookRequest,
    options?: MutationOptions,
  ): Promise<Result<Protocol.NotebookOutput>> {
    return request(this.#target, "notebook.create", {
      body: notebook,
      options,
    });
  }
}
