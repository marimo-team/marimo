/* Copyright 2026 Marimo. All rights reserved. */

import { CatalogEvents, type CatalogEventsOptions } from "./catalog/events.ts";
import type { CatalogKind } from "./kinds.ts";
import { NotebookClient } from "./notebook/client.ts";
import type * as Protocol from "./protocol.ts";
import {
  below,
  type ClientOptions,
  type MutationOptions,
  request,
  resolve,
  type Result,
  type Target,
} from "./request.ts";

/** A client for a host's API, without a retained catalog. */
export class Client {
  readonly #target: Target<"">;

  public constructor(url: string | URL, init: ClientOptions = {}) {
    this.#target = { url: new URL(url), prefix: "", client: init };
  }

  /** The host API's base URL. Each read returns a copy. */
  public get url(): URL {
    return new URL(this.#target.url);
  }

  /** Follow the catalog with this client's options and an independent cursor. */
  public events<const K extends CatalogKind = CatalogKind>(
    options: Omit<CatalogEventsOptions<K>, keyof ClientOptions> = {},
  ): CatalogEvents<K> {
    return new CatalogEvents<K>(below(this.#target.url, "/events"), {
      ...this.#target.client,
      ...options,
    });
  }

  /**
   * Address a notebook by id or catalog record, sharing this client's options.
   *
   * Makes no request and retains no metadata. The id belongs to this host.
   */
  public notebook(
    notebook: Protocol.NotebookId | Pick<Protocol.NotebookOutput, "id">,
  ): NotebookClient {
    const id = typeof notebook === "string" ? notebook : notebook.id;
    return new NotebookClient(
      resolve(this.#target, "/notebooks/{notebook_id}", { notebook_id: id }),
      this.#target.client,
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
