/* Copyright 2026 Marimo. All rights reserved. */

import { Effect } from "effect";
import { HttpApiBuilder } from "effect/http-api";
import * as Problems from "../Problems.ts";
import * as Host from "../Host.ts";

// @ts-expect-error A decision error must carry the questions to answer.
new Problems.DecisionRequiredProblem({});
// @ts-expect-error A failed precondition must carry the current document and cell.
new Problems.PreconditionFailedProblem({});
// @ts-expect-error Unrelated errors cannot carry decision fields.
new Problems.NotFoundProblem({ decisions: [] });

export function checkNarrowing(error: typeof Problems.Problem.Type) {
  if (error._tag === "PreconditionFailedProblem") {
    return error.document;
  }
  if (error._tag === "DecisionRequiredProblem") {
    return error.decisions;
  }
  if (error._tag === "NotFoundProblem") {
    // @ts-expect-error An unrelated error has no decisions field.
    return error.decisions;
  }
}

HttpApiBuilder.handler(Host.Api, "Notebook", "save", () =>
  Effect.fail(new Problems.DecisionRequiredProblem({ decisions: [] })),
);
HttpApiBuilder.handler(Host.Api, "Notebook", "save", () =>
  // @ts-expect-error Saving does not require a runtime.
  Effect.fail(new Problems.NoRuntimeProblem()),
);

const notFound = new Problems.NotFoundProblem();
const notFoundTag: "NotFoundProblem" = notFound._tag;
const recovered: Effect.Effect<string> = Effect.fail(notFound).pipe(
  Effect.catchTag(notFoundTag, (error) => Effect.succeed(error.title)),
);
Effect.fail(notFound).pipe(
  // @ts-expect-error Only declared error tags can be handled.
  Effect.catchTag("UnauthorizedProblem", () => Effect.succeed("wrong tag")),
);
// @ts-expect-error A known error cannot carry another problem's status.
new Problems.NotFoundProblem({ status: 409 });
new Problems.NotFoundProblem({
  // @ts-expect-error A known error cannot carry another problem's type.
  type: "urn:marimo:problem:conflict",
});
void recovered;
