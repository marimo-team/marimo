/* Copyright 2026 Marimo. All rights reserved. */

import type * as z from "zod";
import { type OperationId, operations } from "./operations.ts";
import * as Protocol from "./protocol.ts";

/** How a client reaches and authenticates with a host. */
export interface ClientOptions {
  /** Sent as `Authorization: Bearer <token>`. */
  readonly token?: string;
  /**
   * Sends each request. Defaults to `globalThis.fetch`.
   *
   * Wrap it to add headers or change requests. It receives each request with
   * the client's own headers already set.
   */
  readonly fetch?: typeof globalThis.fetch;
}

/**
 * The outcome of a request the host answered.
 *
 * A request throws when the host cannot be reached or when its answer is not
 * one the protocol describes.
 */
export type Result<T> =
  | { readonly ok: true; readonly status: number; readonly data: T }
  | {
      readonly ok: false;
      readonly status: number;
      readonly problem: Protocol.ProblemOutput;
    };

/** Options for a request that changes state. */
export interface MutationOptions {
  readonly signal?: AbortSignal;
  /**
   * The key the host uses to answer a repeated request once.
   *
   * Defaults to a new random key. Pass the same key to retry a request.
   */
  readonly idempotencyKey?: string;
}

/** The operations a client calls as requests rather than streams. */
type RequestOperationId = {
  [Id in OperationId]: (typeof operations)[Id]["responses"] extends {
    200: "text/event-stream";
  }
    ? never
    : Id;
}[OperationId];

/** The request operations whose paths start with `prefix`. */
export type OperationsBelow<Prefix extends string> = {
  [Id in RequestOperationId]: (typeof operations)[Id]["path"] extends
    | Prefix
    | `${Prefix}/${string}`
    ? Id
    : never;
}[RequestOperationId];

/**
 * Where a client's requests go.
 *
 * `url` stands for `prefix`, so each operation's path below `prefix` resolves
 * below `url` and keeps its query string.
 */
export interface Target<Prefix extends string> {
  readonly url: URL;
  readonly prefix: Prefix;
  readonly client: ClientOptions;
}

/** What a request reads from each entry of the operations table. */
interface Operation {
  readonly method: string;
  readonly path: string;
  readonly headers: Readonly<Record<string, boolean>>;
  readonly body: z.ZodType | null;
  readonly responses: Readonly<
    Record<number, z.ZodType | null | "text/event-stream">
  >;
}

const table: Readonly<Record<OperationId, Operation>> = operations;

type Entry<Id extends RequestOperationId> = (typeof operations)[Id];

/** The data of each success response an operation describes. */
type Data<Id extends RequestOperationId> = {
  [
    Status in keyof Entry<Id>["responses"]
  ]: Entry<Id>["responses"][Status] extends z.ZodType
    ? z.output<Entry<Id>["responses"][Status]>
    : undefined;
}[keyof Entry<Id>["responses"]];

/** What a request sends besides its operation. */
interface Call<Id extends RequestOperationId> {
  /** Values for the placeholders in the path below the target's prefix. */
  readonly params?: Readonly<Record<string, string>>;
  readonly body?: Entry<Id>["body"] extends z.ZodType
    ? z.input<Entry<Id>["body"]>
    : undefined;
  readonly headers?: Readonly<Record<string, string | undefined>>;
  readonly options?: MutationOptions;
}

/**
 * A random key for a request that changes state.
 *
 * Send it again with a retry whose outcome is unknown, so the host applies the
 * request once. `crypto.randomUUID` exists only in secure contexts, such as
 * pages served over HTTPS or from localhost. A host on a local network is
 * often neither.
 */
export function idempotencyKey(): string {
  if (typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4),
    hex.slice(4, 6),
    hex.slice(6, 8),
    hex.slice(8, 10),
    hex.slice(10),
  ]
    .map((group) => group.join(""))
    .join("-");
}

/** Whether a `Content-Type` names `type`, ignoring case and parameters. */
export function isType(contentType: string | null, type: string): boolean {
  return contentType?.split(";", 1)[0].trim().toLowerCase() === type;
}

/**
 * A URL below `url`, keeping its query string.
 *
 * `suffix` is empty or starts with a slash, as the protocol's paths do.
 */
export function below(url: URL, suffix: string): URL {
  const target = new URL(url);
  target.pathname = url.pathname.replace(/\/$/, "") + suffix;
  return target;
}

/** The URL an operation's path resolves to below the target. */
export function resolve<Prefix extends string>(
  target: Target<Prefix>,
  path: string,
  params: Readonly<Record<string, string>>,
): URL {
  const suffix = path
    .slice(target.prefix.length)
    .replace(/\{(\w+)\}/g, (_, name: string) => {
      const value = params[name];
      // An empty or dot segment would name a different resource, and
      // percent-encoding does not stop URLs from resolving dot segments.
      if (
        value === undefined ||
        value === "" ||
        value === "." ||
        value === ".."
      ) {
        throw new Error(`${path} needs a valid ${name}`);
      }
      return encodeURIComponent(value);
    });
  return below(target.url, suffix);
}

/**
 * Send one request and decode the host's answer.
 *
 * The body is validated before it is sent, and the response is validated
 * against the schema the protocol gives its status, so the data has the type
 * the operation describes.
 */
export async function request<
  Prefix extends string,
  Id extends OperationsBelow<Prefix>,
>(
  target: Target<Prefix>,
  id: Id,
  { params = {}, body, headers = {}, options = {} }: Call<Id>,
): Promise<Result<Data<Id>>> {
  const operation = table[id];
  const { client } = target;
  const sent = new Headers();
  sent.set("Accept", "application/json, application/problem+json");
  if (client.token !== undefined) {
    sent.set("Authorization", `Bearer ${client.token}`);
  }
  if ("Idempotency-Key" in operation.headers) {
    sent.set("Idempotency-Key", options.idempotencyKey ?? idempotencyKey());
  }
  for (const [name, value] of Object.entries(headers)) {
    if (value !== undefined) {
      sent.set(name, value);
    }
  }
  let payload: string | undefined;
  if (operation.body !== null) {
    sent.set("Content-Type", "application/json");
    payload = JSON.stringify(operation.body.parse(body));
  }
  const fetch = client.fetch ?? globalThis.fetch;
  const response = await fetch(resolve(target, operation.path, params), {
    method: operation.method,
    headers: sent,
    body: payload,
    signal: options.signal,
  });
  const status = response.status;
  const schema = operation.responses[status];
  if (schema === null) {
    return { ok: true, status, data: undefined as Data<Id> };
  }
  if (schema !== undefined && schema !== "text/event-stream") {
    const data = schema.parse(await response.json()) as Data<Id>;
    return { ok: true, status, data };
  }
  const type = response.headers.get("Content-Type");
  if (!response.ok && isType(type, "application/problem+json")) {
    const problem = Protocol.Problem.parse(await response.json());
    return { ok: false, status, problem };
  }
  throw new Error(`Unexpected ${status} response to ${id}`);
}
