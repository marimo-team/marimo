/* Copyright 2026 Marimo. All rights reserved. */

import { Cause, Clock, Effect, Ref, Schema, Stream } from "effect";
import { Sse } from "effect/encoding";
import { HttpServerResponse } from "effect/http";
import {
  AnalysisNotebookEvent,
  CatalogEvent,
  eventCodec,
  NotebookStreamEvent,
} from "./events.ts";
import { Internal, Problem } from "./errors.ts";

const encodeProblem = Schema.encodeSync(Schema.fromJsonString(Problem));

function eventResponse<A>(
  schema: Schema.Codec<A, unknown>,
  source: Stream.Stream<A, Problem>,
): HttpServerResponse.HttpServerResponse {
  const encode = Schema.encodeEffect(eventCodec(schema));
  const body = Stream.unwrap(
    Effect.gen(function* () {
      const lastEvent = yield* Ref.make(yield* Clock.currentTimeMillis);
      const events = source.pipe(
        Stream.mapEffect((value) => encode(value)),
        Stream.map((value) =>
          Sse.encoder.write({ _tag: "Event", ...value, id: value.id }),
        ),
        Stream.tap(() =>
          Effect.flatMap(Clock.currentTimeMillis, (now) =>
            Ref.set(lastEvent, now),
          ),
        ),
        Stream.catchCause((cause) => {
          if (Cause.hasInterruptsOnly(cause)) return Stream.failCause(cause);
          const error = cause.reasons.find(Cause.isFailReason)?.error;
          const problem = Schema.is(Problem)(error) ? error : new Internal({});
          return Stream.succeed(
            Sse.encoder.write({
              _tag: "Event",
              event: "effect/httpapi/stream/failure",
              id: undefined,
              data: encodeProblem(problem),
            }),
          );
        }),
      );
      const heartbeat = Stream.tick("15 seconds").pipe(
        Stream.filterEffect(() =>
          Effect.gen(function* () {
            return (
              (yield* Clock.currentTimeMillis) - (yield* Ref.get(lastEvent)) >=
              15000
            );
          }),
        ),
        Stream.map(() => ": ping\n\n"),
      );
      return events.pipe(
        Stream.merge(heartbeat, { haltStrategy: "left" }),
        Stream.encodeText,
      );
    }),
  );
  return HttpServerResponse.stream(body, {
    contentType: "text/event-stream",
    headers: { "cache-control": "no-cache", "x-accel-buffering": "no" },
  });
}

export const catalogEvents = (stream: Stream.Stream<CatalogEvent, Problem>) =>
  eventResponse(CatalogEvent, stream);
export const notebookEvents = (
  stream: Stream.Stream<NotebookStreamEvent, Problem>,
) => eventResponse(NotebookStreamEvent, stream);
export const analysisNotebookEvents = (
  stream: Stream.Stream<AnalysisNotebookEvent, Problem>,
) => eventResponse(AnalysisNotebookEvent, stream);
