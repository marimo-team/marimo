/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";

export const ProjectId = Schema.NonEmptyString.annotate({
  identifier: "ProjectId",
});
export type ProjectId = typeof ProjectId.Type;
export const NotebookId = Schema.NonEmptyString.annotate({
  identifier: "NotebookId",
});
export type NotebookId = typeof NotebookId.Type;
export const RuntimeId = Schema.NonEmptyString.annotate({
  identifier: "RuntimeId",
});
export type RuntimeId = typeof RuntimeId.Type;
export const AttachmentId = Schema.NonEmptyString.annotate({
  identifier: "AttachmentId",
});
export type AttachmentId = typeof AttachmentId.Type;
export const RunId = Schema.NonEmptyString.annotate({ identifier: "RunId" });
export type RunId = typeof RunId.Type;
export const ExecutionId = Schema.NonEmptyString.annotate({
  identifier: "ExecutionId",
});
export type ExecutionId = typeof ExecutionId.Type;
export const ItemId = Schema.NonEmptyString.annotate({ identifier: "ItemId" });
export type ItemId = typeof ItemId.Type;
export const CellId = Schema.NonEmptyString.annotate({ identifier: "CellId" });
export type CellId = typeof CellId.Type;
export const Etag = Schema.String.annotate({ identifier: "Etag" });
export type Etag = typeof Etag.Type;
export const CodeFingerprint = Schema.NonEmptyString.annotate({
  identifier: "CodeFingerprint",
});
export type CodeFingerprint = typeof CodeFingerprint.Type;

function isTimestamp(value: string): boolean {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:[Zz]|[+-](\d{2}):(\d{2}))$/.exec(
      value,
    );
  if (!match) return false;
  const [
    ,
    year,
    month,
    day,
    hour,
    minute,
    second,
    offsetHour = "0",
    offsetMinute = "0",
  ] = match;
  const y = Number(year);
  const days = [
    31,
    y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ];
  return (
    Number(month) >= 1 &&
    Number(month) <= 12 &&
    Number(day) >= 1 &&
    Number(day) <= days[Number(month) - 1] &&
    Number(hour) < 24 &&
    Number(minute) < 60 &&
    Number(second) <= 60 &&
    Number(offsetHour) < 24 &&
    Number(offsetMinute) < 60
  );
}
export const Timestamp = Schema.String.check(
  Schema.makeFilter(isTimestamp, {
    expected: "an RFC 3339 timestamp",
    toJsonSchema: () => ({ format: "date-time" }),
  }),
);
export const NonNegativeInt = Schema.Int.check(
  Schema.isGreaterThanOrEqualTo(0),
);
export const PositiveInt = Schema.Int.check(Schema.isGreaterThanOrEqualTo(1));
export const Empty = Schema.Record(Schema.String, Schema.Never);
