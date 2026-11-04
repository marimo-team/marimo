/* Copyright 2026 Marimo. All rights reserved. */

import { Effect } from "effect";
import { HttpApiBuilder } from "effect/http-api";
import { Host } from "../index.ts";

// @ts-expect-error Only declared operation names can be implemented.
HttpApiBuilder.handler(Host.api, "host", "notebookCreate", () => Effect.void);

HttpApiBuilder.handler(Host.api, "host", "notebook.create", () =>
  // @ts-expect-error A successful create must return a complete notebook.
  Effect.succeed({ id: "n1" }),
);

HttpApiBuilder.handler(Host.api, "host", "notebook.create", () =>
  // @ts-expect-error Handler failures must be declared by the contract.
  Effect.fail(new Error("unexpected")),
);

HttpApiBuilder.group(Host.api, "host", (handlers) =>
  // @ts-expect-error A group must implement all its operations.
  handlers.handle("notebook.delete", () => Effect.void),
);
