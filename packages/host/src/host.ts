/* Copyright 2026 Marimo. All rights reserved. */

import { Layer } from "effect";
import { HttpApiBuilder } from "effect/http-api";
import { HostApi as api } from "./api.ts";
import { problemsLayer } from "./server.ts";

export { api };
export { HostAuthorization as Authorization } from "./api.ts";

export const problems = problemsLayer(api);

export function layer<A, E, R>(handlers: Layer.Layer<A, E, R>) {
  return HttpApiBuilder.layer(api).pipe(
    Layer.provide(handlers),
    Layer.provideMerge(problems),
  );
}
