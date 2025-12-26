/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-redeclare */
import { Deferred } from "@/utils/Deferred";
import { generateUUID } from "@/utils/uuid";
import type { TypedString } from "../../utils/typed";

export type RequestId = TypedString<"RequestId">;
export const RequestId = {
  create(): RequestId {
    return generateUUID() as RequestId;
  },
};

/**
 * Helper class to manage deferred requests.
 * We send a request via HTTP and then wait for the response from the kernel
 * via a websocket.
 */
export class DeferredRequestRegistry<REQ, RES> {
  public requests = new Map<RequestId, Deferred<RES>>();
  public operation: string;
  private makeRequest: (id: RequestId, req: REQ) => Promise<void>;
  private opts: {
    /**
     * Resolve existing requests with an empty response.
     */
    resolveExistingRequests?: () => RES;
  };

  constructor(
    operation: string,
    makeRequest: (id: RequestId, req: REQ) => Promise<void>,
    opts: {
      /**
       * Resolve existing requests with an empty response.
       */
      resolveExistingRequests?: () => RES;
    } = {},
  ) {
    this.operation = operation;
    this.makeRequest = makeRequest;
    this.opts = opts;
  }

  async request(opts: REQ): Promise<RES> {
    if (this.opts.resolveExistingRequests) {
      const result = this.opts.resolveExistingRequests();
      for (const deferred of this.requests.values()) {
        deferred.resolve(result);
      }
      this.requests.clear();
    }

    const requestId = RequestId.create();
    const deferred = new Deferred<RES>();

    this.requests.set(requestId, deferred);

    await this.makeRequest(requestId, opts).catch((error) => {
      deferred.reject(error);
      this.requests.delete(requestId);
    });
    return deferred.promise;
  }

  resolve(requestId: RequestId, response: RES) {
    const entry = this.requests.get(requestId);
    if (entry === undefined) {
      return;
    }

    entry.resolve(response);
    this.requests.delete(requestId);
  }

  reject(requestId: RequestId, error: Error) {
    const entry = this.requests.get(requestId);
    if (entry === undefined) {
      return;
    }

    entry.reject(error);
    this.requests.delete(requestId);
  }
}
