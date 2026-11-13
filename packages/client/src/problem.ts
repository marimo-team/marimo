/* Copyright 2026 Marimo. All rights reserved. */

import * as Protocol from "./protocol.ts";

const knownTypes = new Set<string>(
  Protocol.Problem.options.flatMap((problem) => problem.shape.type.options),
);

/** An unrecognized problem, handled by status while retaining its original URI. */
export interface UnknownProblem {
  readonly type: "unknown";
  readonly uri: string;
  readonly status: number;
  readonly title: string;
  readonly detail?: string;
}

/** Known problems retain their required fields when narrowed by `type`. */
export type Problem = Protocol.ProblemOutput | UnknownProblem;

export function parseProblem(value: unknown): Problem {
  const { type, ...fields } = Protocol.UnknownProblem.parse(value);
  if (knownTypes.has(type)) {
    return Protocol.Problem.parse(value);
  }
  return { type: "unknown", uri: type, ...fields };
}
