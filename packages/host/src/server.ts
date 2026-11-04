/* Copyright 2026 Marimo. All rights reserved. */

import { Cause, Effect, Layer, Schema, type Types } from "effect";
import { HttpApiError, HttpApi, type HttpApiGroup } from "effect/http-api";
import { HttpRouter, HttpServerError, HttpServerResponse } from "effect/http";
import { HostProblems } from "./api.ts";
import {
  Internal,
  InvalidRequest,
  MethodNotAllowed,
  NotAcceptable,
  NotFound,
  Problem,
} from "./errors.ts";

function problemResponse(problem: Problem, headers?: Record<string, string>) {
  return HttpServerResponse.jsonUnsafe(Schema.encodeSync(Problem)(problem), {
    status: problem.status,
    contentType: "application/problem+json",
    headers,
  });
}

const HostProblemsLive = Layer.succeed(HostProblems, (effect) =>
  effect.pipe(
    Effect.catchCause(
      (
        cause,
      ): Effect.Effect<never, Types.unhandled | InvalidRequest | Internal> => {
        for (const reason of cause.reasons) {
          if (
            Cause.isFailReason(reason) &&
            HttpApiError.HttpApiSchemaError.is(reason.error)
          ) {
            return Effect.fail(
              reason.error.kind === "Body" ||
                reason.error.kind === "ResponseHeaders"
                ? new Internal({})
                : new InvalidRequest({
                    detail: `Invalid request ${reason.error.kind.toLowerCase()}.`,
                  }),
            );
          }
          if (
            Cause.isFailReason(reason) &&
            HttpServerError.isHttpServerError(reason.error) &&
            reason.error.reason._tag === "RequestParseError"
          ) {
            return Effect.fail(
              new InvalidRequest({ detail: "Invalid request body." }),
            );
          }
        }
        if (Cause.hasDies(cause)) return Effect.fail(new Internal({}));
        return Effect.failCause(cause);
      },
    ),
  ),
);

export function problemsLayer<
  Id extends string,
  Groups extends HttpApiGroup.Constraint,
>(api: HttpApi.HttpApi<Id, Groups>) {
  return Layer.merge(HostProblemsLive, routerProblemsLayer(api));
}

function routerProblemsLayer<
  Id extends string,
  Groups extends HttpApiGroup.Constraint,
>(api: HttpApi.HttpApi<Id, Groups>) {
  const routes: Array<{ method: string; pattern: RegExp }> = [];
  HttpApi.reflect(api, {
    onGroup: () => {},
    onEndpoint: ({ endpoint }) => {
      const pattern = endpoint.path
        .split("/")
        .map((part) =>
          part.startsWith(":")
            ? "[^/]+"
            : part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
        )
        .join("/");
      routes.push({
        method: endpoint.method,
        pattern: new RegExp(`^${pattern}/?$`),
      });
    },
  });
  return HttpRouter.middleware<{
    handles: HttpServerError.HttpServerError;
  }>()(
    (effect) =>
      effect.pipe(
        Effect.catch((error) => {
          if (!HttpServerError.isHttpServerError(error))
            return Effect.fail(error);
          if (error.reason._tag === "RouteNotFound") {
            const path = new URL(error.request.url, "http://localhost")
              .pathname;
            const allowed = routes
              .filter((route) => route.pattern.test(path))
              .map((route) => route.method);
            return Effect.succeed(
              allowed.length
                ? problemResponse(new MethodNotAllowed({}), {
                    allow: [...new Set(allowed)].join(", "),
                  })
                : problemResponse(new NotFound({})),
            );
          }
          return Effect.succeed(
            problemResponse(
              error.reason._tag === "RequestParseError"
                ? new InvalidRequest({})
                : new Internal({}),
            ),
          );
        }),
        Effect.map((response) => {
          if (
            response.headers["content-type"]?.startsWith(
              "application/problem+json",
            )
          )
            return response;
          if (response.status === 415)
            return problemResponse(
              new InvalidRequest({ detail: "Expected application/json." }),
            );
          if (response.status === 406)
            return problemResponse(new NotAcceptable({}));
          if (response.status === 500) return problemResponse(new Internal({}));
          return response;
        }),
      ),
    { global: true },
  );
}
